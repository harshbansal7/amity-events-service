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
from app.models.user import User  # Import here to avoid circular imports
from app.models.external_participant import ExternalParticipant

class Event:
    def __init__(self, mongo):
        self.mongo = mongo
        self.collection = self.mongo.db.users
        self.events_collection = self.mongo.db.events
        self.user_model = User(mongo)

    def create_event(self, event_data, creator_id):
        def generate_event_code():
            import string, random
            chars = string.ascii_uppercase + string.digits
            return ''.join(random.choices(chars, k=6))

        event = {
            'name': event_data['name'],
            'date': event_data['date'],
            'max_participants': event_data['max_participants'],
            'venue': event_data['venue'],
            'description': event_data['description'],
            'prizes': event_data.get('prizes', []),
            'creator_id': creator_id,
            'participants': [],
            'created_at': datetime.now(),
            'image_url': event_data.get('image_url', None),
            'allow_external': event_data.get('allow_external', False),
            'event_code': generate_event_code() if event_data.get('allow_external') else None,
            'external_participants': []  # Separate list for external participants
        }
        minutes = int(event_data.get('duration_minutes') or 0)
        hours = int(event_data.get('duration_hours') or 0) 
        days = int(event_data.get('duration_days') or 0)

        # Convert all to minutes then extract days/hours/minutes
        total_minutes = minutes + (hours * 60) + (days * 24 * 60)
        days, remainder = divmod(total_minutes, 24 * 60)
        hours, minutes = divmod(remainder, 60)

        event['duration'] = {
            'days': days,
            'hours': hours, 
            'minutes': minutes
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
        
        # Check if user is already registered (in either old or new format)
        is_registered = any(
            (isinstance(p, dict) and p['enrollment_number'] == user_id)
            for p in event['participants']
        )
        
        if is_registered:
            return False, "Already registered"
            
        if len(event['participants']) >= int(event['max_participants']):
            return False, "Event is full"

        # Add participant with registration timestamp and attendance status
        registration = {
            'enrollment_number': user_id,
            'registered_at': datetime.now(),
            'attendance': False  # Default attendance status
        }

        self.events_collection.update_one(
            {'_id': ObjectId(event_id)},
            {'$push': {'participants': registration}}
        )
        return True, "Successfully registered"

    def delete_event(self, event_id, user_id):
        event = self.get_event_by_id(event_id)
        if not event:
            return False, "Event not found"
        
        if str(event['creator_id']) != str(user_id):
            return False, "Unauthorized: Only event creator can delete this event"
        
        # Delete associated external participants
        external_participant_model = ExternalParticipant(self.mongo)
        external_participant_model.delete_by_event(event_id)
        
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
        
        # Check if user is registered (in either old or new format)
        is_registered = any(
            (isinstance(p, dict) and p['enrollment_number'] == user_id)
            for p in event['participants']
        )
        
        if not is_registered:
            return False, "Not registered for this event"

        # Remove participant using both formats in one query
        result = self.events_collection.update_one(
            {'_id': ObjectId(event_id)},
            {'$pull': {
                'participants': {'enrollment_number': user_id}
            }}
        )
        
        if result.modified_count:
            # If external participant, remove from external_participants collection
            if user_id.startswith('EXT'):
                from app.models.external_participant import ExternalParticipant
                external_model = ExternalParticipant(self.mongo)
                external_model.collection.delete_one({'temp_enrollment': user_id})
            return True, "Successfully unregistered"
        return False, "Failed to unregister"

    def get_registered_events(self, user_id):
        # Query for both old and new format
        events = list(self.events_collection.find({
            '$or': [
                {'participants': user_id},  # Old format
                {'participants.enrollment_number': user_id}  # New format
            ]
        }))
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

    def get_event_participants(self, event_id):
        event = self.get_event_by_id(event_id)
        if not event:
            return []

        participants = []
        for participant_data in event['participants']:
            # Handle both old format (string) and new format (dict)
            if isinstance(participant_data, str):
                enrollment_number = participant_data
                registered_at = datetime.now()
                attendance = False
            else:
                enrollment_number = participant_data['enrollment_number']
                registered_at = participant_data['registered_at']
                attendance = participant_data.get('attendance', False)

            # First try to get from regular users
            user = self.user_model.get_user_by_enrollment(enrollment_number)
            
            # If not found, try to get from external participants
            if not user and enrollment_number.startswith('EXT'):
                from app.models.external_participant import ExternalParticipant
                external_model = ExternalParticipant(self.mongo)
                user = external_model.get_by_temp_enrollment(enrollment_number)
                if user:
                    # Format external user data to match regular user structure
                    user = {
                        'name': user['name'],
                        'enrollment_number': user['temp_enrollment'],
                        'amity_email': user['email'],  # Use regular email for external users
                        'branch': 'External',
                        'year': '-',
                        'phone_number': user['phone_number']
                    }

            if user:
                participants.append({
                    'name': user['name'],
                    'enrollment_number': user['enrollment_number'],
                    'amity_email': user['amity_email'],
                    'branch': user['branch'],
                    'year': user['year'],
                    'phone_number': user['phone_number'],
                    'registered_at': registered_at,
                    'attendance': attendance
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
            'enrollment_number': 'Enrollment Number',
            'amity_email': 'Amity Email',
            'phone_number': 'Phone Number',
            'branch': 'Branch',
            'year': 'Year',
            'registered_at': 'Registration Date',
            'attendance': 'Attendance Status'
        }
        
        # Parse fields_printed from comma-separated string
        selected_fields = fields_printed.split(',') if fields_printed else list(all_fields.keys())
        
        # Always include enrollment_number if not already included
        if 'enrollment_number' not in selected_fields:
            selected_fields.insert(0, 'enrollment_number')
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30)
        elements = []
        
        # Create headers based on selected fields
        headers = ['No.'] + [all_fields[field] for field in selected_fields]
        
        # Create table data
        data = [headers]
        for idx, participant in enumerate(participants, 1):
            row = [idx]
            for field in selected_fields:
                value = participant[field]
                if field == 'registered_at':
                    value = value.strftime("%d/%m/%Y %I:%M %p")
                elif field == 'attendance':
                    value = 'Present' if value else 'Absent'
                row.append(value)
            data.append(row)
        
        # Calculate column widths based on content
        available_width = 535  # Adjusted for margins
        num_columns = len(headers)
        col_widths = [25]  # Smaller width for No. column
        
        # Distribute remaining width based on content type with adjusted percentages
        field_widths = {
            'name': 0.18,  # Increased for longer names
            'enrollment_number': 0.15,
            'amity_email': 0.20,  # Increased for longer email addresses
            'phone_number': 0.12,
            'branch': 0.08,  # Reduced as usually shorter
            'year': 0.05,   # Reduced as just a number
            'registered_at': 0.15,  # Increased for date format
            'attendance': 0.07  # Add width for attendance column
        }
        
        remaining_width = available_width - 25
        for field in selected_fields:
            col_widths.append(remaining_width * field_widths[field])
        
        # Create table with calculated widths
        table = Table(data, colWidths=col_widths)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),  # No. column centered
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),    # Name left-aligned
            ('ALIGN', (2, 0), (2, -1), 'LEFT'),    # Enrollment left-aligned
            ('ALIGN', (3, 0), (3, -1), 'LEFT'),    # Email left-aligned
            ('ALIGN', (4, 0), (-1, -1), 'CENTER'), # Rest centered
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),     # Slightly smaller font
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('WORDWRAP', (0, 0), (-1, -1), True),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.lightgrey])
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
            'enrollment_number': 'Enrollment Number',
            'amity_email': 'Amity Email',
            'phone_number': 'Phone Number',
            'branch': 'Branch',
            'year': 'Year',
            'registered_at': 'Registration Date',
            'attendance': 'Attendance Status'
        }
        
        # Parse fields_printed from comma-separated string
        selected_fields = fields_printed.split(',') if fields_printed else list(all_fields.keys())
        
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
                    value = value.strftime("%d/%m/%Y %I:%M %p")
                elif field == 'attendance':
                    value = 'Present' if value else 'Absent'
                worksheet.write(row, col, value)
        
        workbook.close()
        output.seek(0)
        return output

    def mark_attendance(self, event_id, enrollment_number, status):
        """Mark attendance for a participant"""
        result = self.events_collection.update_one(
            {
                '_id': ObjectId(event_id),
                'participants.enrollment_number': enrollment_number
            },
            {'$set': {'participants.$.attendance': status}}
        )
        
        if result.modified_count:
            return True, "Attendance marked successfully"
        return False, "Failed to mark attendance"