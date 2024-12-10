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
            if not all(field in data and data[field] != '' for field in required_fields):
                return jsonify({'message': 'Missing required fields'}), 400

            try:
                parsed_date = parse(data['date'])
                data['date'] = parsed_date.replace(tzinfo=None) + timedelta(hours=5, minutes=30)
            except ValueError:
                return jsonify({'message': 'Invalid date format'}), 400

            # Convert allow_external string to boolean
            if 'allow_external' in data:
                data['allow_external'] = data['allow_external'].lower() == 'true'

            # Handle image upload
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

        except Exception as e:
            return jsonify({'message': f'Error creating event: {str(e)}'}), 500

    @events_bp.route('/events', methods=['GET'])
    @token_required
    def get_events(current_user, **kwargs):
        # If external participant, only show their registered event
        if kwargs.get('is_external'):
            event = event_model.get_event_by_id(kwargs.get('event_id'))
            return json.loads(json_util.dumps({'events': [event] if event else []})), 200

        events = event_model.get_all_events()
        return json.loads(json_util.dumps({'events': events})), 200

    @events_bp.route('/events/<event_id>/register', methods=['POST'])
    @token_required
    def register_for_event(current_user, event_id, **kwargs):
        success, message = event_model.register_participant(event_id, current_user)
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
        """Get list of participants for an event"""
        
        event = event_model.events_collection.find_one({'_id': ObjectId(event_id)})
        if not event or event['creator_id'] != current_user:
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
        if not event or event['creator_id'] != current_user:
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
        if not event or event['creator_id'] != current_user:
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

    @events_bp.route('/events/<event_id>/participants/<enrollment_number>/attendance', methods=['POST'])
    @token_required
    def mark_attendance(current_user, event_id, enrollment_number):
        # Get the event
        event = event_model.get_event_by_id(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
            
        # Only event creator can mark attendance
        if str(event['creator_id']) != str(current_user):
            return jsonify({'error': 'Unauthorized'}), 403

        data = request.get_json()
        status = data.get('status', False)
        
        success, message = event_model.mark_attendance(event_id, enrollment_number, status)
        if success:
            return jsonify({'message': message}), 200
        return jsonify({'error': message}), 400

    return events_bp 