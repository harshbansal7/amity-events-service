from datetime import timedelta
from flask import Blueprint, request, jsonify, current_app
from app.utils.auth_middleware import token_required
from app.models.event import Event
from app.utils.file_upload import FAILED_FILE_URL, save_image
from dateutil.parser import parse
from bson import json_util
import json
import os

events_bp = Blueprint('events', __name__)

def init_event_routes(mongo):
    event_model = Event(mongo)

    @events_bp.route('/events', methods=['POST'])
    @token_required
    def create_event(current_user):
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
    def get_events(current_user):
        events = event_model.get_all_events()
        # Convert BSON to JSON using json_util
        return json.loads(json_util.dumps({'events': events})), 200

    @events_bp.route('/events/<event_id>/register', methods=['POST'])
    @token_required
    def register_for_event(current_user, event_id):
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
            print(message)
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
    def unregister_from_event(current_user, event_id):
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

    return events_bp 