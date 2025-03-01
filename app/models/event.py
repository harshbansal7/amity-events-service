from datetime import datetime, timezone
from bson import ObjectId, json_util
import json
from dateutil.parser import parse
import pandas as pd
from io import BytesIO
from fpdf import FPDF
import xlsxwriter
from app.models.user import User  # Import here to avoid circular imports
from app.models.external_participant import ExternalParticipant
import random
import string
import secrets
from config import Config

class PDF(FPDF):
    def header(self):
        # Transparent
        self.set_fill_color(215, 183, 255)  # Indigo with 10% opacity
        self.rect(0, 0, self.w, 50, 'F')

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', align='C')

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
            
        # Generate approval token - used for approving the event
        approval_token = secrets.token_urlsafe(32)
        
        # If using existing code, verify it exists
        if event_data.get('use_existing_code') and event_data.get('existing_event_code'):
            existing_event = self.events_collection.find_one({
                'event_code': event_data['existing_event_code'],
                'allow_external': True
            })
            if not existing_event:
                raise ValueError('Invalid existing event code')
            event_code = event_data['existing_event_code']
        else:
            event_code = generate_event_code() if event_data.get('allow_external') else None
            
        # Check if kill switch is enabled (default: True)
        require_approval = getattr(Config, 'EVENT_APPROVAL_REQUIRED', True)
            
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
            'event_code': event_code,
            'external_participants': [],
            'custom_fields': event_data.get('custom_fields', []).split(','),
            'is_approved': not require_approval,  # Auto-approved if kill switch is off
            'approval_status': 'approved' if not require_approval else 'pending',
            'approval_token': approval_token,
            'approval_request_time': datetime.now(),
            'approval_time': None if require_approval else datetime.now()
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
        return result.inserted_id, approval_token

    def get_all_events(self, include_pending=False):
        # If include_pending is False, only show approved events
        filter_query = {} if include_pending else {'is_approved': True}
        events = list(self.events_collection.find(filter_query))
        # Convert ObjectId to string for each event
        for event in events:
            event['_id'] = str(event['_id'])
            if 'date' in event and not isinstance(event['date'], str):
                event['date'] = event['date'].isoformat()
            if 'created_at' in event and not isinstance(event['created_at'], str):
                event['created_at'] = event['created_at'].isoformat()
        return events
    
    def get_pending_events(self):
        events = list(self.events_collection.find({'approval_status': 'pending'}))
        # Convert ObjectId to string for each event
        for event in events:
            event['_id'] = str(event['_id'])
            if 'date' in event and not isinstance(event['date'], str):
                event['date'] = event['date'].isoformat()
            if 'created_at' in event and not isinstance(event['created_at'], str):
                event['created_at'] = event['created_at'].isoformat()
        return events
        
    def approve_event(self, event_id, token):
        """Approve an event using the approval token"""
        event = self.events_collection.find_one({
            '_id': ObjectId(event_id),
            'approval_token': token,
            'approval_status': 'pending'
        })
        
        if not event:
            return False, "Invalid token or event already approved"
            
        # Update the event to approved status
        result = self.events_collection.update_one(
            {'_id': ObjectId(event_id)},
            {'$set': {
                'is_approved': True,
                'approval_status': 'approved',
                'approval_time': datetime.now()
            }}
        )
        
        if result.modified_count:
            return True, "Event approved successfully"
        return False, "Failed to approve event"
    
    def reject_event(self, event_id, token, reason=None):
        """Reject an event using the approval token"""
        event = self.events_collection.find_one({
            '_id': ObjectId(event_id),
            'approval_token': token,
            'approval_status': 'pending'
        })
        
        if not event:
            return False, "Invalid token or event not in pending status"
            
        # Update the event to rejected status
        result = self.events_collection.update_one(
            {'_id': ObjectId(event_id)},
            {'$set': {
                'is_approved': False,
                'approval_status': 'rejected',
                'rejection_reason': reason,
                'approval_time': datetime.now()
            }}
        )
        
        if result.modified_count:
            return True, "Event rejected successfully"
        return False, "Failed to reject event"

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

    def register_participant(self, event_id, enrollment_number, custom_field_values):
        event = self.get_event_by_id(event_id)
        if not event:
            return False, 'Event not found'
            
        # Check if event is approved
        if not event.get('is_approved', False):
            return False, 'Event is not approved yet'

        # Check if already registered
        if any(p.get('enrollment_number', p) == enrollment_number for p in event['participants']):
            return False, 'Already registered for this event'

        # Check max participants limit
        if len(event['participants']) >= int(event['max_participants']):
            return False, 'Event is full'

        # Get participant details
        participant = self.user_model.get_user_by_enrollment(enrollment_number) or \
                     self.external_participants_collection.find_one({'temp_enrollment': enrollment_number})
        
        if not participant:
            return False, 'Participant not found'

        # Create participant entry with custom fields
        participant_entry = {
            'enrollment_number': enrollment_number,
            'name': participant.get('name', ''),
            'amity_email': participant.get('amity_email', participant.get('email', '')),
            'branch': participant.get('branch', ''),
            'year': participant.get('year', ''),
            'phone_number': participant.get('phone_number', ''),
            'registered_at': datetime.now(timezone.utc),
            'attendance': False,
            'custom_field_values': custom_field_values
        }

        self.events_collection.update_one(
            {'_id': ObjectId(event_id)},
            {'$push': {'participants': participant_entry}}
        )

        return True, 'Successfully registered for event'

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
        allowed_fields = ['name', 'date', 'max_participants', 'venue', 'description', 'prizes', 'image_url', 'custom_fields']
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
                custom_field_values = {}
            else:
                enrollment_number = participant_data['enrollment_number']
                registered_at = participant_data['registered_at']
                attendance = participant_data.get('attendance', False)
                custom_field_values = participant_data.get('custom_field_values', {})

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
                    'attendance': attendance,
                    'custom_field_values': custom_field_values
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
        
        # Add custom fields to all_fields if they exist in any participant
        custom_fields = set()
        for participant in participants:
            if participant.get('custom_field_values'):
                custom_fields.update(participant['custom_field_values'].keys())
        
        for field in custom_fields:
            all_fields[f'custom_{field}'] = field
        
        # Parse fields_printed from comma-separated string
        selected_fields = fields_printed.split(',') if fields_printed else list(all_fields.keys())
        
        # Create PDF
        pdf = PDF('P', 'mm', 'A4')
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        
        # Get event details
        event = self.get_event_by_id(event_id)
        
        # Event Title
        pdf.set_font('Arial', 'B', 24)
        pdf.set_text_color(79, 70, 229)  # Indigo-600
        pdf.cell(0, 15, event['name'], align='C', ln=True)
        
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
        
        # Event Info Box
        pdf.set_fill_color(243, 244, 246)  # Gray-100
        pdf.set_draw_color(229, 231, 235)  # Gray-200
        
        info_box_y = pdf.get_y() + 5
        info_box_height = 25
        pdf.rect(15, info_box_y, pdf.w - 30, info_box_height, 'DF')
        
        # Info text
        pdf.set_font('Arial', '', 10)
        pdf.set_text_color(55, 65, 81)  # Gray-700
        
        # Calculate widths for three columns
        col_width = (pdf.w - 30) / 3
        
        pdf.set_xy(15, info_box_y + 5)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(col_width, 5, 'Date & Time:', align='C')
        pdf.set_font('Arial', '', 10)
        pdf.set_xy(15, info_box_y + 12)
        pdf.cell(col_width, 5, formatted_date, align='C')
        
        pdf.set_xy(15 + col_width, info_box_y + 5)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(col_width, 5, 'Venue:', align='C')
        pdf.set_font('Arial', '', 10)
        pdf.set_xy(15 + col_width, info_box_y + 12)
        pdf.cell(col_width, 5, event['venue'], align='C')
        
        pdf.set_xy(15 + 2 * col_width, info_box_y + 5)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(col_width, 5, 'Participants:', align='C')
        pdf.set_font('Arial', '', 10)
        pdf.set_xy(15 + 2 * col_width, info_box_y + 12)
        pdf.cell(col_width, 5, f"{len(participants)} / {event['max_participants']}", align='C')
        
        # Participants List Header
        pdf.ln(35)
        pdf.set_font('Arial', 'B', 14)
        pdf.set_text_color(31, 41, 55)  # Gray-800
        pdf.cell(0, 10, 'Participants List', ln=True)
        
        # Table headers
        pdf.set_fill_color(249, 250, 251)  # Gray-50
        pdf.set_font('Arial', 'B', 10)
        
        # Calculate column widths
        col_widths = []
        total_width = pdf.w - 30
        
        for field in selected_fields:
            if field == 'enrollment_number':
                col_widths.append(total_width * 0.15)
            elif field == 'name':
                col_widths.append(total_width * 0.2)
            elif field == 'amity_email':
                col_widths.append(total_width * 0.25)
            else:
                col_widths.append(total_width * 0.15)
        
        # Draw headers
        pdf.set_x(15)
        for i, field in enumerate(selected_fields):
            pdf.cell(col_widths[i], 10, all_fields[field], 1, 0, 'L', True)
        pdf.ln()
        
        # Table data
        pdf.set_font('Arial', '', 10)
        pdf.set_fill_color(255, 255, 255)  # White
        
        for i, participant in enumerate(participants):
            if pdf.get_y() + 10 > pdf.page_break_trigger:
                pdf.add_page()
                # Redraw headers
                pdf.set_font('Arial', 'B', 10)
                pdf.set_x(15)
                for j, field in enumerate(selected_fields):
                    pdf.cell(col_widths[j], 10, all_fields[field], 1, 0, 'L', True)
                pdf.ln()
                pdf.set_font('Arial', '', 10)
            
            pdf.set_x(15)
            for j, field in enumerate(selected_fields):
                if field.startswith('custom_'):
                    # Handle custom field values
                    custom_field = field[7:]  # Remove 'custom_' prefix
                    value = participant.get('custom_field_values', {}).get(custom_field, '-')
                else:
                    value = participant[field]
                
                if field == 'registered_at':
                    value = value.strftime("%d/%m/%Y %I:%M %p")
                elif field == 'attendance':
                    value = 'Present' if value else 'Absent'
                
                pdf.cell(col_widths[j], 10, str(value), 1, 0, 'L', i % 2 == 0)
            pdf.ln()
        
        buffer = BytesIO()
        pdf.output(buffer)
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
        
        # Add custom fields
        custom_fields = set()
        for participant in participants:
            if participant.get('custom_field_values'):
                custom_fields.update(participant['custom_field_values'].keys())
        
        for field in custom_fields:
            all_fields[f'custom_{field}'] = field
        
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
                if field.startswith('custom_'):
                    # Handle custom field values
                    custom_field = field[7:]  # Remove 'custom_' prefix
                    value = participant.get('custom_field_values', {}).get(custom_field, '-')
                else:
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

    def get_events_by_code(self, event_code):
        """Get all events with matching event code"""
        events = list(self.events_collection.find({
            'event_code': event_code,
            'allow_external': True
        }))
        
        for event in events:
            event['_id'] = str(event['_id'])
            if 'date' in event and not isinstance(event['date'], str):
                event['date'] = event['date'].isoformat()
            if 'created_at' in event and not isinstance(event['created_at'], str):
                event['created_at'] = event['created_at'].isoformat()
        return events

    def mark_batch_attendance(self, event_id, attendance_data):
        """Mark attendance for multiple participants at once"""
        try:
            for record in attendance_data:
                self.events_collection.update_one(
                    {
                        '_id': ObjectId(event_id),
                        'participants.enrollment_number': record['enrollment_number']
                    },
                    {'$set': {'participants.$.attendance': record['attendance']}}
                )
            return True, "Attendance marked successfully"
        except Exception as e:
            print(f"Error marking batch attendance: {str(e)}")
            return False, "Failed to mark attendance"