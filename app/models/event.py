from datetime import datetime
from bson import ObjectId, json_util
import json
from dateutil.parser import parse
import pandas as pd
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
import xlsxwriter

class Event:
    def __init__(self, mongo):
        self.mongo = mongo
        self.collection = self.mongo.db.users
        self.events_collection = self.mongo.db.events

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
            'created_at': datetime.now(),
            'image_url': event_data.get('image_url', None)
        }
        result = self.events_collection.insert_one(event)
        return result.inserted_id

    def get_all_events(self):
        events = list(self.events_collection.find())
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
            event = self.events_collection.find_one({'_id': ObjectId(event_id)})
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

        self.events_collection.update_one(
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
        result = self.events_collection.delete_one({'_id': ObjectId(event_id)})
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
        allowed_fields = ['name', 'date', 'max_participants', 'venue', 'description', 'prizes', 'image_url']
        duration_fields = ['duration_days', 'duration_hours', 'duration_minutes']

        # Handle non-duration fields
        update_fields.update({
            field: update_data[field] 
            for field in allowed_fields 
            if field in update_data
        })

        # Handle duration fields if any are present
        if any(field in update_data for field in duration_fields):
            minutes = int(update_data.get('duration_minutes') or 0)
            hours = int(update_data.get('duration_hours') or 0) 
            days = int(update_data.get('duration_days') or 0)

            # Convert all to minutes then extract days/hours/minutes
            total_minutes = minutes + (hours * 60) + (days * 24 * 60)
            days, remainder = divmod(total_minutes, 24 * 60)
            hours, minutes = divmod(remainder, 60)

            update_fields['duration'] = {
                'days': days,
                'hours': hours, 
                'minutes': minutes
            }
            
        if not update_fields:
            return False, "No valid fields to update"
        
        # Update the event
        result = self.events_collection.update_one(
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

        result = self.events_collection.update_one(
            {'_id': ObjectId(event_id)},
            {'$pull': {'participants': user_id}}
        )
        
        if result.modified_count:
            return True, "Successfully unregistered"
        return False, "Failed to unregister"

    def get_registered_events(self, user_id):
        events = list(self.events_collection.find({'participants': user_id}))
        for event in events:
            event['_id'] = str(event['_id'])
            if 'date' in event and not isinstance(event['date'], str):
                event['date'] = event['date'].isoformat()
            if 'created_at' in event and not isinstance(event['created_at'], str):
                event['created_at'] = event['created_at'].isoformat()
        return events

    def get_created_events(self, user_id):
        events = list(self.events_collection.find({'creator_id': user_id}))
        for event in events:
            event['_id'] = str(event['_id'])
            if 'date' in event and not isinstance(event['date'], str):
                event['date'] = event['date'].isoformat()
            if 'created_at' in event and not isinstance(event['created_at'], str):
                event['created_at'] = event['created_at'].isoformat()
        return events

    def get_event_participants(self, event_id, fields_printed=None):
        """Get detailed information about all participants of an event"""
        event = self.events_collection.find_one({'_id': ObjectId(event_id)})
        if not event:
            return None

        participants = []
        for enrollment_number in event.get('participants', []):
            user = self.collection.find_one(
                {'enrollment_number': enrollment_number},
                {'password': 0}  # Exclude password
            )
            if user:
                participants.append({
                    'enrollment_number': user['enrollment_number'],
                    'name': user['name'],
                    'email': user['email'],
                    'branch': user['branch'],
                    'year': user['year'],
                    'registered_at': user.get('created_at')
                })

        return participants

    def generate_pdf_report(self, event_id, fields_printed=None):
        """Generate PDF report of participants with selected fields"""
        participants = self.get_event_participants(event_id)
        if not participants:
            return None

        # Define all possible fields and their display names
        all_fields = {
            'name': 'Name',
            'enrollment_number': 'Enrollment',
            'branch': 'Branch',
            'year': 'Year',
            'email': 'Email',
            'registered_at': 'Registration Date'
        }
        
        # Parse fields_printed from comma-separated string
        selected_fields = fields_printed.split(',') if fields_printed else list(all_fields.keys())
        
        # Always include enrollment_number if not already included
        if 'enrollment_number' not in selected_fields:
            selected_fields.insert(0, 'enrollment_number')
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        
        # Create headers based on selected fields
        headers = ['No.'] + [all_fields[field] for field in selected_fields]
        
        # Create table data
        data = [headers]
        for idx, participant in enumerate(participants, 1):
            row = [idx]
            for field in selected_fields:
                if field == 'registered_at':
                    row.append(participant[field].strftime("%Y-%m-%d %H:%M"))
                else:
                    row.append(participant[field])
            data.append(row)
        
        # Calculate column widths based on number of fields
        available_width = 560  # Total available width
        num_columns = len(headers)
        col_widths = [30]  # Width for No. column
        
        remaining_width = available_width - 30
        field_width = remaining_width / (num_columns - 1)
        col_widths.extend([field_width] * (num_columns - 1))
        
        # Create table with calculated widths
        table = Table(data, colWidths=col_widths)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(table)
        doc.build(elements)
        
        buffer.seek(0)
        return buffer

    def generate_excel_report(self, event_id, fields_printed=None):
        """Generate Excel report of participants with selected fields"""
        participants = self.get_event_participants(event_id)
        if not participants:
            return None
        
        # Define all possible fields and their display names
        all_fields = {
            'name': 'Name',
            'enrollment_number': 'Enrollment',
            'branch': 'Branch',
            'year': 'Year',
            'email': 'Email',
            'registered_at': 'Registration Date'
        }
        
        # Parse fields_printed from comma-separated string
        selected_fields = fields_printed.split(',') if fields_printed else list(all_fields.keys())
        print(selected_fields)
        # Always include enrollment_number if not already included
        if 'enrollment_number' not in selected_fields:
            selected_fields.insert(0, 'enrollment_number')
        
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet()
        
        # Write headers
        headers = ['No.'] + [all_fields[field] for field in selected_fields]
        for col, header in enumerate(headers):
            worksheet.write(0, col, header)
        
        # Write data
        for row, participant in enumerate(participants, 1):
            worksheet.write(row, 0, row)  # Write row number
            for col, field in enumerate(selected_fields, 1):
                value = participant[field]
                if field == 'registered_at':
                    value = value.strftime("%Y-%m-%d %H:%M")
                worksheet.write(row, col, value)
        
        workbook.close()
        output.seek(0)
        return output