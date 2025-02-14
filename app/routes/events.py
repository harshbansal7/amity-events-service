from datetime import timedelta
from flask import Blueprint, request, jsonify, current_app, send_file
from app.utils.auth_middleware import token_required
from app.models.event import Event
from app.utils.file_upload import FAILED_FILE_URL, save_image
from dateutil.parser import parse
from bson import json_util, ObjectId
import json
import os
from datetime import datetime

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
                
            event_id = event_model.create_event(data, current_user)
            return jsonify({
                'message': 'Event created successfully',
                'event_id': str(event_id)
            }), 201

        except ValueError as e:
            return jsonify({'message': str(e)}), 400
        except Exception as e:
            return jsonify({'message': f'Error creating event: {str(e)}'}), 500

    @events_bp.route('/events', methods=['GET'])
    @token_required
    def get_events(current_user, **kwargs):
        # If external participant, show all events with matching code
        if kwargs.get('is_external'):
            events = event_model.get_events_by_code(kwargs.get('event_code'))
            return json.loads(json_util.dumps({'events': events})), 200

        events = event_model.get_all_events()
        return json.loads(json_util.dumps({'events': events})), 200

    @events_bp.route('/events/<event_id>/register', methods=['POST'])
    @token_required
    def register_for_event(current_user, event_id, **kwargs):
        data = request.get_json()
        custom_field_values = json.loads(data.get('custom_field_values', '{}')) if data else {}
        success, message = event_model.register_participant(event_id, current_user, custom_field_values)
        if success:
            return jsonify({'message': message}), 200
        return jsonify({'message': message}), 400

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