from datetime import datetime, timezone
from bson import ObjectId
import string
import random

class ExternalParticipant:
    def __init__(self, mongo):
        self.mongo = mongo
        self.collection = self.mongo.db.external_participants

    def generate_temp_credentials(self):
        # Generate temporary enrollment number with 'EXT' prefix
        temp_id = 'EXT' + ''.join(random.choices(string.digits, k=8))
        # Generate temporary password
        temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        return temp_id, temp_password

    def create_external_participant(self, participant_data, event_id, password_hash):
        participant = {
            'name': participant_data['name'],
            'email': participant_data['email'],
            'phone_number': participant_data['phone_number'],
            'temp_enrollment': participant_data['temp_enrollment'],
            'password': password_hash,
            'event_id': event_id,
            'created_at': datetime.now(timezone.utc),
            'is_external': True
        }
        result = self.collection.insert_one(participant)
        return result.inserted_id

    def get_by_temp_enrollment(self, temp_enrollment):
        return self.collection.find_one({'temp_enrollment': temp_enrollment})

    def delete_by_event(self, event_id):
        """Delete all external participants for an event"""
        self.collection.delete_many({'event_id': event_id}) 