from datetime import timedelta
from flask import Blueprint, request, jsonify, current_app, send_file, url_for
from app.utils.auth_middleware import token_required
from app.models.event import Event
from app.utils.file_upload import FAILED_FILE_URL, save_image
from dateutil.parser import parse
from bson import json_util, ObjectId
import json
import os
from app.utils.mail import MailgunMailer
from datetime import datetime
from config import Config

mailer = MailgunMailer()
events_bp = Blueprint('events', __name__)

def init_event_routes(mongo):
    event_model = Event(mongo)
    
    @events_bp.route('/events', methods=['POST'])
    @token_required
    def create_event(current_user, **kwargs):
        # Prevent external participants from creating events
        if kwargs.get('is_external'):
            return jsonify({'message': 'External participants cannot create events'}), 403
        try:
            # Get creator details
            creator = mongo.db.users.find_one({'enrollment_number': current_user})
            if not creator:
                return jsonify({'message': 'Creator not found'}), 404
                
            # Handle form data
            data = request.form.to_dict()
            
            # Check required fields
            required_fields = ['name', 'date', 'max_participants', 'venue']
            missing_fields = [field for field in required_fields if field not in data or data[field] == '']
            if missing_fields:
                return jsonify({'message': f'Missing required fields: {", ".join(missing_fields)}'}), 400
                
            # Convert boolean fields
            data['allow_external'] = data.get('allow_external', 'false').lower() == 'true'
            data['use_existing_code'] = data.get('use_existing_code', 'false').lower() == 'true'
            
            # Validate existing code if specified
            if data.get('use_existing_code') and not data.get('existing_event_code'):
                return jsonify({'message': 'Event code is required when using existing code'}), 400
                
            try:
                parsed_date = parse(data['date'])
                data['date'] = parsed_date.replace(tzinfo=None) + timedelta(hours=5, minutes=30)
            except ValueError:
                return jsonify({'message': 'Invalid date format'}), 400
                
            if 'image' in request.files:
                file = request.files['image']
                image_url = save_image(file)
                if image_url:
                    data['image_url'] = image_url
            else:
                data['image_url'] = FAILED_FILE_URL
            
            # Create event and get approval token
            event_id, approval_token = event_model.create_event(data, current_user)
            
            # Check if approval is required
            require_approval = getattr(Config, 'EVENT_APPROVAL_REQUIRED', True)
            
            if require_approval:
                # Get event data
                event = event_model.get_event_by_id(str(event_id))
                
                # Send approval email to admin
                admin_email = getattr(Config, 'ADMIN_EMAIL', 'admin@example.com')
                approve_url = f"{getattr(Config, 'FRONTEND_URL', '')}/admin/approve-event/{event_id}?token={approval_token}"
                
                mailer.send_event_approval_request(
                    to_email=admin_email,
                    event_data=event,
                    creator_data=creator,
                    approval_url=approve_url,
                    token=approval_token
                )
                
                # Send pending notification to event creator
                mailer.send_event_pending_notification(
                    to_email=creator.get('amity_email'),
                    event_name=data['name'],
                    event_date=data['date'].strftime("%B %d, %Y at %I:%M %p") if isinstance(data['date'], datetime) else data['date']
                )
                
                return jsonify({
                    'message': 'Event created successfully and pending approval. You will be notified once approved.',
                    'event_id': str(event_id),
                    'approval_status': 'pending'
                }), 201
            else:
                return jsonify({
                    'message': 'Event created successfully',
                    'event_id': str(event_id),
                    'approval_status': 'approved'
                }), 201
                
        except ValueError as e:
            return jsonify({'message': str(e)}), 400
        except Exception as e:
            return jsonify({'message': f'Error creating event: {str(e)}'}), 500

    @events_bp.route('/events', methods=['GET'])
    @token_required
    def get_events(current_user, **kwargs):
        try:
            # Determine if pending events should be included
            # Only include_pending if user is admin
            is_admin = current_user == getattr(Config, 'ADMIN_USER_ID', None)
            # include_pending = is_admin
            
            # If external participant, show all events with matching code
            if kwargs.get('is_external'):
                events = event_model.get_events_by_code(kwargs.get('event_code'))
                # Filter out sensitive data
                for event in events:
                    event['participants'] = len(event.get('participants', []))
                return json.loads(json_util.dumps({'events': events})), 200
                
            # Get all events, filtering by approval status
            events = event_model.get_all_events(include_pending=False)
            
            # Filter sensitive data based on whether user is creator
            for event in events:
                if str(event.get('creator_id')) != str(current_user):
                    # For non-creators, only send participant count and registration status
                    is_registered = any(
                        p.get('enrollment_number') == current_user 
                        for p in event.get('participants', [])
                    )
                    participant_count = len(event.get('participants', []))
                    event['participants'] = participant_count
                    event['is_registered'] = is_registered
                # Creators see full participant data for their events
            return json.loads(json_util.dumps({'events': events})), 200
            
        except Exception as e:
            return jsonify({'error': f'Error fetching events: {str(e)}'}), 500
            
    @events_bp.route('/admin/events/pending', methods=['GET'])
    @token_required
    def get_pending_events(current_user):
        # Only admin can see pending events
        if current_user != getattr(Config, 'ADMIN_USER_ID', None):
            return jsonify({'message': 'Unauthorized access'}), 403
            
        try:
            events = event_model.get_pending_events()
            return json.loads(json_util.dumps({'events': events})), 200
        except Exception as e:
            return jsonify({'message': f'Error fetching pending events: {str(e)}'}), 500
            
    @events_bp.route('/admin/events/<event_id>/approve', methods=['GET', 'POST'])
    def approve_event(event_id):
        try:
            # Handle direct approval from email link (GET request with token in query param)
            if request.method == 'GET':
                token = request.args.get('token')
                if not token:
                    return jsonify({'message': 'Token is required'}), 400
                    
                # Approve the event
                success, message = event_model.approve_event(event_id, token)
                
                if success:
                    # Get event and creator details
                    event = event_model.get_event_by_id(event_id)
                    creator = mongo.db.users.find_one({'enrollment_number': event.get('creator_id')})
                    
                    if creator and event:
                        # Send confirmation to creator
                        mailer.send_event_approval_confirmation(
                            to_email=creator.get('amity_email'),
                            event_name=event.get('name'),
                            is_approved=True
                        )
                    
                    # Return HTML page with success message instead of JSON
                    html_response = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Event Approval</title>
                        <style>
                            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; text-align: center; }}
                            .container {{ max-width: 600px; margin: 40px auto; padding: 20px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
                            .success {{ color: #28a745; }}
                            h1 {{ color: #4A90E2; }}
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <h1>Event Approval</h1>
                            <h2 class="success">Success!</h2>
                            <p>{message}</p>
                            <p>The event organizer has been notified.</p>
                        </div>
                    </body>
                    </html>
                    """
                    return html_response, 200, {'Content-Type': 'text/html'}
                
                # Return HTML page with error message
                html_error = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Event Approval</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; text-align: center; }}
                        .container {{ max-width: 600px; margin: 40px auto; padding: 20px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
                        .error {{ color: #dc3545; }}
                        h1 {{ color: #4A90E2; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>Event Approval</h1>
                        <h2 class="error">Error</h2>
                        <p>{message}</p>
                    </div>
                </body>
                </html>
                """
                return html_error, 400, {'Content-Type': 'text/html'}
            
            # Handle POST request from API (requires authentication)
            else:
                # Only admin can approve events via POST
                @token_required
                def approve_as_admin(current_user):
                    if current_user != getattr(Config, 'ADMIN_USER_ID', None):
                        return jsonify({'message': 'Unauthorized access'}), 403
                        
                    data = request.get_json()
                    token = data.get('token')
                    
                    if not token:
                        return jsonify({'message': 'Token is required'}), 400
                        
                    # Approve the event
                    success, message = event_model.approve_event(event_id, token)
                    
                    if success:
                        # Get event and creator details
                        event = event_model.get_event_by_id(event_id)
                        creator = mongo.db.users.find_one({'enrollment_number': event.get('creator_id')})
                        
                        if creator and event:
                            # Send confirmation to creator
                            mailer.send_event_approval_confirmation(
                                to_email=creator.get('amity_email'),
                                event_name=event.get('name'),
                                is_approved=True
                            )
                        
                        return jsonify({'message': message}), 200
                    return jsonify({'message': message}), 400
                
                return approve_as_admin()
                
        except Exception as e:
            error_message = f'Error approving event: {str(e)}'
            if request.method == 'GET':
                html_error = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Event Approval</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; text-align: center; }}
                        .container {{ max-width: 600px; margin: 40px auto; padding: 20px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
                        .error {{ color: #dc3545; }}
                        h1 {{ color: #4A90E2; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>Event Approval</h1>
                        <h2 class="error">System Error</h2>
                        <p>{error_message}</p>
                    </div>
                </body>
                </html>
                """
                return html_error, 500, {'Content-Type': 'text/html'}
            return jsonify({'message': error_message}), 500

    @events_bp.route('/admin/events/<event_id>/reject', methods=['POST'])
    @token_required
    def reject_event(current_user, event_id):
        # Only admin can reject events
        if current_user != getattr(Config, 'ADMIN_USER_ID', None):
            return jsonify({'message': 'Unauthorized access'}), 403
            
        try:
            data = request.get_json()
            token = data.get('token')
            reason = data.get('reason', '')
            
            if not token:
                return jsonify({'message': 'Token is required'}), 400
                
            # Reject the event
            success, message = event_model.reject_event(event_id, token, reason)
            
            if success:
                # Get event and creator details
                event = event_model.get_event_by_id(event_id)
                creator = mongo.db.users.find_one({'enrollment_number': event.get('creator_id')})
                
                if creator and event:
                    # Send rejection notification to creator
                    mailer.send_event_approval_confirmation(
                        to_email=creator.get('amity_email'),
                        event_name=event.get('name'),
                        is_approved=False,
                        rejection_reason=reason
                    )
                
                return jsonify({'message': message}), 200
            return jsonify({'message': message}), 400
            
        except Exception as e:
            return jsonify({'message': f'Error rejecting event: {str(e)}'}), 500
    
    @events_bp.route('/events/<event_id>/approval-status', methods=['GET'])
    @token_required
    def get_approval_status(current_user, event_id):
        try:
            event = event_model.get_event_by_id(event_id)
            
            if not event:
                return jsonify({'message': 'Event not found'}), 404
                
            # Only creator or admin can check approval status
            is_admin = current_user == getattr(Config, 'ADMIN_USER_ID', None)
            
            if str(event.get('creator_id')) != str(current_user) and not is_admin:
                return jsonify({'message': 'Unauthorized access'}), 403
                
            return jsonify({
                'approval_status': event.get('approval_status', 'unknown'),
                'is_approved': event.get('is_approved', False),
                'rejection_reason': event.get('rejection_reason', None),
                'approval_request_time': event.get('approval_request_time'),
                'approval_time': event.get('approval_time')
            }), 200
            
        except Exception as e:
            return jsonify({'message': f'Error fetching approval status: {str(e)}'}), 500

    @events_bp.route('/events/<event_id>/register', methods=['POST'])
    @token_required
    def register_for_event(current_user, event_id, **kwargs):
        try:
            data = request.get_json()
            custom_field_values = json.loads(data.get('custom_field_values', '{}')) if data else {}
            # Get event details
            event = event_model.get_event_by_id(event_id)
            if not event:
                return jsonify({'message': 'Event not found'}), 404
                
            # Check if event is approved
            if not event.get('is_approved', False):
                return jsonify({'message': 'This event is pending approval and not available for registration yet'}), 403
            
            # Get user details for email
            user = mongo.db.users.find_one({'enrollment_number': current_user})
            if not user:
                return jsonify({'message': 'User not found'}), 404
                
            organizer = mongo.db.users.find_one({'enrollment_number': event['creator_id']})
            if not organizer:
                return jsonify({'message': 'Organizer not found'}), 404
            
            # Register the user
            success, message = event_model.register_participant(event_id, current_user, custom_field_values)
            if not success:
                return jsonify({'message': message}), 400
                
            # Format date
            if isinstance(event['date'], str):
                try:
                    event_date = datetime.strptime(event['date'], "%Y-%m-%dT%H:%M:%S.%f")
                except ValueError:
                    try:
                        event_date = datetime.strptime(event['date'], "%Y-%m-%dT%H:%M:%S")
                    except ValueError:
                        event_date = datetime.now()  # fallback
            else:
                event_date = event['date']
            
            formatted_date = event_date.strftime("%B %d, %Y at %I:%M %p")
            
            # Send confirmation email to participant
            mailer.send_event_registration_confirmation(
                to_email=user['amity_email'],
                name=user['name'],
                event_name=event['name'],
                event_date=formatted_date,
                venue=event['venue'],
                organizer_email=organizer['amity_email']
            )
            
            # Send notification email to organizer
            mailer.send_event_registration_notification(
                to_email=organizer['amity_email'],
                name=user['name'],
                event_name=event['name']
            )
            
            return jsonify({'message': message}), 200
        except Exception as e:
            return jsonify({'message': f'Error registering for event: {str(e)}'}), 500

    @events_bp.route('/events/<event_id>', methods=['DELETE'])
    @token_required
    def delete_event(current_user, event_id):
        try:
            success, message = event_model.delete_event(event_id, current_user)
            if success:
                return jsonify({'message': message}), 200
            return jsonify({'message': message}), 403
        except Exception as e:
            return jsonify({'message': f'Error deleting event: {str(e)}'}), 500

    @events_bp.route('/events/<event_id>', methods=['PUT'])
    @token_required
    def update_event(current_user, event_id):
        try:
            # Handle form data and file upload
            data = request.form.to_dict()
            
            try:
                parsed_date = parse(data['date'])
                data['date'] = parsed_date.replace(tzinfo=None) + timedelta(hours=5, minutes=30)
            except ValueError:
                return jsonify({'message': 'Invalid date format'}), 400

            if data.get('has_image_been_changed', 'false').lower() == 'true':
                if 'image' in request.files:
                    file = request.files['image']
                    image_url = save_image(file)
                    if image_url:
                        data['image_url'] = image_url
                else:
                    data['image_url'] = FAILED_FILE_URL
                
            success, message = event_model.update_event(event_id, current_user, data)
            if success:
                return jsonify({'message': message}), 200
            return jsonify({'message': message}), 403
            
        except Exception as e:
            return jsonify({'message': f'Error updating event: {str(e)}'}), 500

    @events_bp.route('/events/<event_id>', methods=['GET'])
    @token_required
    def get_event(current_user, event_id):
        try:
            event = event_model.get_event_by_id(event_id)
            if event:
                return json.loads(json_util.dumps(event)), 200
            return jsonify({'message': 'Event not found'}), 404
        except Exception as e:
            return jsonify({'message': f'Error fetching event: {str(e)}'}), 500

    @events_bp.route('/events/<event_id>/unregister', methods=['POST'])
    @token_required
    def unregister_from_event(current_user, event_id, **kwargs):
        try:
            success, message = event_model.unregister_participant(event_id, current_user)
            if success:
                return jsonify({'message': message}), 200
            return jsonify({'message': message}), 400
        except Exception as e:
            return jsonify({'message': f'Error unregistering from event: {str(e)}'}), 500

    @events_bp.route('/events/registered', methods=['GET'])
    @token_required
    def get_registered_events(current_user):
        try:
            events = event_model.get_registered_events(current_user)
            return json.loads(json_util.dumps({'events': events})), 200
        except Exception as e:
            return jsonify({'message': f'Error fetching registered events: {str(e)}'}), 500

    @events_bp.route('/events/created', methods=['GET'])
    @token_required
    def get_created_events(current_user):
        try:
            events = event_model.get_created_events(current_user)
            return json.loads(json_util.dumps({'events': events})), 200
        except Exception as e:
            return jsonify({'message': f'Error fetching created events: {str(e)}'}), 500

    @events_bp.route('/events/<event_id>/participants', methods=['GET'])
    @token_required
    def get_participants(current_user, event_id):
        """Get participants for an event"""
        
        # Check if user is the event creator
        event = event_model.events_collection.find_one({'_id': ObjectId(event_id)})
        if not event or str(event['creator_id']) != str(current_user):
            return jsonify({'message': 'Unauthorized access'}), 403
        
        participants = event_model.get_event_participants(event_id)
        
        if participants is None:
            return jsonify({'message': 'Event not found'}), 404
        
        return jsonify(participants)

    @events_bp.route('/events/<event_id>/participants/pdf', methods=['GET'])
    @token_required
    def download_pdf(current_user, event_id):
        """Download participants list as PDF"""
        
        # Check if user is the event creator
        event = event_model.events_collection.find_one({'_id': ObjectId(event_id)})
        if not event or str(event['creator_id']) != str(current_user):
            return jsonify({'message': 'Unauthorized access'}), 403
        
        # Get fields to be printed from query parameters
        fields_printed = request.args.get('fields_printed')
        
        pdf_buffer = event_model.generate_pdf_report(event_id, fields_printed)
        if pdf_buffer is None:
            return jsonify({'message': 'Event not found'}), 404
        
        return send_file(
            pdf_buffer,
            download_name=f'participants_{event_id}_{datetime.now().strftime("%Y%m%d")}.pdf',
            mimetype='application/pdf'
        )

    @events_bp.route('/events/<event_id>/participants/excel', methods=['GET'])
    @token_required
    def download_excel(current_user, event_id):
        """Download participants list as Excel"""
        
        # Check if user is the event creator
        event = event_model.events_collection.find_one({'_id': ObjectId(event_id)})
        if not event or str(event['creator_id']) != str(current_user):
            return jsonify({'message': 'Unauthorized access'}), 403
        
        # Get fields to be printed from query parameters
        fields_printed = request.args.get('fields_printed')
        
        excel_buffer = event_model.generate_excel_report(event_id, fields_printed)
        if excel_buffer is None:
            return jsonify({'message': 'Event not found'}), 404
        
        return send_file(
            excel_buffer,
            download_name=f'participants_{event_id}_{datetime.now().strftime("%Y%m%d")}.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    @events_bp.route('/events/<event_id>/participants/<enrollment_number>', methods=['DELETE'])
    @token_required
    def unregister_participant(current_user, event_id, enrollment_number):
        """Unregister a participant from an event"""
        
        # Check if user is the event creator
        event = event_model.events_collection.find_one({'_id': ObjectId(event_id)})
        if not event or event['creator_id'] != current_user:
            return jsonify({'message': 'Unauthorized access'}), 403
        
        if event_model.unregister_participant(event_id, enrollment_number):
            return jsonify({'message': 'Participant unregistered successfully'})
        return jsonify({'message': 'Failed to unregister participant'}), 400

    @events_bp.route('/events/<event_id>/attendance', methods=['POST'])
    @token_required
    def mark_attendance(current_user, event_id):
        # Get the event
        event = event_model.get_event_by_id(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
            
        # Only event creator can mark attendance
        if str(event['creator_id']) != str(current_user):
            return jsonify({'error': 'Unauthorized'}), 403

        data = request.get_json()
        attendance_data = data.get('attendance', [])
        
        success, message = event_model.mark_batch_attendance(event_id, attendance_data)
        if success:
            return jsonify({'message': message}), 200
        return jsonify({'error': message}), 400

    @events_bp.route('/events/<event_id>/participants', methods=['POST'])
    @token_required
    def update_participant_details(current_user, event_id):
        """Update participant's custom field values"""
        try:
            data = request.get_json()
            enrollment_number = data.get('enrollment_number')
            custom_field_values = data.get('custom_field_values', {})

            if not enrollment_number or not custom_field_values:
                return jsonify({'message': 'Missing required fields'}), 400

            # Update the participant's custom field values
            result = event_model.events_collection.update_one(
                {
                    '_id': ObjectId(event_id),
                    'participants.enrollment_number': enrollment_number
                },
                {
                    '$set': {
                        'participants.$.custom_field_values': custom_field_values
                    }
                }
            )

            if result.modified_count:
                return jsonify({'message': 'Participant details updated successfully'}), 200
            return jsonify({'message': 'Failed to update participant details'}), 400

        except Exception as e:
            return jsonify({'message': f'Error updating participant details: {str(e)}'}), 500

    return events_bp