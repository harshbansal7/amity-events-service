from datetime import datetime
from bson import ObjectId, json_util
import json
from dateutil.parser import parse

class Event:
    def __init__(self, mongo):
        self.mongo = mongo
        self.collection = self.mongo.db.events

    def create_event(self, event_data, creator_id):
        event = {
            'name': event_data['name'],
            'date': event_data['date'],
            'duration': {
                'days': event_data.get('duration_days', 0),
                'hours': event_data.get('duration_hours', 0),
                'minutes': event_data.get('duration_minutes', 0)
            },
            'max_participants': event_data['max_participants'],
            'venue': event_data['venue'],
            'description': event_data['description'],
            'prizes': event_data.get('prizes', []),
            'creator_id': creator_id,
            'participants': [],
            'created_at': datetime.utcnow(),
            'image_url': event_data.get('image_url', None)
        }
        result = self.collection.insert_one(event)
        return result.inserted_id

    def get_all_events(self):
        events = list(self.collection.find())
        # Convert ObjectId to string for each event
        for event in events:
            event['_id'] = str(event['_id'])
            if 'date' in event and not isinstance(event['date'], str):
                event['date'] = event['date'].isoformat()
            if 'created_at' in event and not isinstance(event['created_at'], str):
                event['created_at'] = event['created_at'].isoformat()
        return events

    def get_event_by_id(self, event_id):
        try:
            event = self.collection.find_one({'_id': ObjectId(event_id)})
            if event:
                event['_id'] = str(event['_id'])
                if 'date' in event:
                    event['date'] = event['date'].isoformat()
                if 'created_at' in event:
                    event['created_at'] = event['created_at'].isoformat()
            return event
        except:
            return None

    def register_participant(self, event_id, user_id):
        event = self.get_event_by_id(event_id)
        if not event:
            return False, "Event not found"
        
        if user_id in event['participants']:
            return False, "Already registered"
            
        if len(event['participants']) >= int(event['max_participants']):
            return False, "Event is full"

        self.collection.update_one(
            {'_id': ObjectId(event_id)},
            {'$push': {'participants': user_id}}
        )
        return True, "Successfully registered"

    def delete_event(self, event_id, user_id):
        event = self.get_event_by_id(event_id)
        if not event:
            return False, "Event not found"
        
        if str(event['creator_id']) != str(user_id):
            return False, "Unauthorized: Only event creator can delete this event"
        
        # Delete the event
        result = self.collection.delete_one({'_id': ObjectId(event_id)})
        if result.deleted_count:
            return True, "Event deleted successfully"
        return False, "Failed to delete event"

    def update_event(self, event_id, user_id, update_data):
        event = self.get_event_by_id(event_id)
        if not event:
            return False, "Event not found"
        
        if str(event['creator_id']) != str(user_id):
            return False, "Unauthorized: Only event creator can update this event"
        
        # Prepare update data
        update_fields = {}
        allowed_fields = ['name', 'date', 'duration', 'max_participants', 
                         'venue', 'description', 'prizes', 'image_url']
        
        for field in allowed_fields:
            if field in update_data:
                if field == 'date':
                    update_fields[field] = parse(update_data[field])
                elif field == 'duration':
                    update_fields[field] = {
                        'days': update_data.get('duration_days', 0),
                        'hours': update_data.get('duration_hours', 0),
                        'minutes': update_data.get('duration_minutes', 0)
                    }
                else:
                    update_fields[field] = update_data[field]
        
        if not update_fields:
            return False, "No valid fields to update"
        
        # Update the event
        result = self.collection.update_one(
            {'_id': ObjectId(event_id)},
            {'$set': update_fields}
        )
        
        if result.modified_count:
            return True, "Event updated successfully"
        return False, "No changes made to the event"

    def unregister_participant(self, event_id, user_id):
        event = self.get_event_by_id(event_id)
        if not event:
            return False, "Event not found"
        
        if user_id not in event['participants']:
            return False, "Not registered for this event"

        result = self.collection.update_one(
            {'_id': ObjectId(event_id)},
            {'$pull': {'participants': user_id}}
        )
        
        if result.modified_count:
            return True, "Successfully unregistered"
        return False, "Failed to unregister"

    def get_registered_events(self, user_id):
        events = list(self.collection.find({'participants': user_id}))
        for event in events:
            event['_id'] = str(event['_id'])
            if 'date' in event and not isinstance(event['date'], str):
                event['date'] = event['date'].isoformat()
            if 'created_at' in event and not isinstance(event['created_at'], str):
                event['created_at'] = event['created_at'].isoformat()
        return events

    def get_created_events(self, user_id):
        events = list(self.collection.find({'creator_id': user_id}))
        for event in events:
            event['_id'] = str(event['_id'])
            if 'date' in event and not isinstance(event['date'], str):
                event['date'] = event['date'].isoformat()
            if 'created_at' in event and not isinstance(event['created_at'], str):
                event['created_at'] = event['created_at'].isoformat()
        return events