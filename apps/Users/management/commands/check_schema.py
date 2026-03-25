# apps/Users/management/commands/check_schema.py
from django.core.management.base import BaseCommand
from django.db import connection
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Check database schema for User model'

    def handle(self, *args, **options):
        self.stdout.write('Checking User model...')
        
        # Check if table exists
        table_name = User._meta.db_table
        self.stdout.write(f'Table name: {table_name}')
        
        with connection.cursor() as cursor:
            # Check if table exists
            cursor.execute(f"""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='{table_name}'
            """)
            if cursor.fetchone():
                self.stdout.write(self.style.SUCCESS(f'Table {table_name} exists'))
                
                # Get columns
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                self.stdout.write(f'Columns in {table_name}:')
                for col in columns:
                    self.stdout.write(f'  - {col[1]}')
            else:
                self.stdout.write(self.style.ERROR(f'Table {table_name} does NOT exist'))