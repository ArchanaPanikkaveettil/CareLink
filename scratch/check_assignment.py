
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CareLink.settings')
django.setup()

from apps.Requests.models import CareRequest
from apps.assignments.models import CareAssignment
from apps.Applications.models import CareApplication

all_reqs = CareRequest.objects.all()
print(f"Total Requests: {all_reqs.count()}")
for r in all_reqs:
    print(f"REQ {r.id}: Status={r.status}, Caretaker={r.assigned_caretaker}, Patient={r.patient_name}")

assignments = CareAssignment.objects.all()
print(f"\nTotal Assignments: {assignments.count()}")
for a in assignments:
    print(f"ASGN {a.id}: Req={a.care_request_id if a.care_request else 'N/A'}, Caretaker={a.caretaker}, Status={a.status}")
