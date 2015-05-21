import json
import unicodecsv

from datetime import datetime
from django.contrib.auth.decorators import login_required
from django.contrib.sites.models import get_current_site
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from symposion.proposals.models import ProposalBase
from symposion.reviews.views import access_not_permitted
from symposion.schedule.models import Slot


def json_serializer(obj):
    if isinstance(obj, datetime.time):
        return obj.strftime("%H:%M")
    raise TypeError


def duration(start, end):
    start_dt = datetime.strptime(start.isoformat(), "%H:%M:%S")
    end_dt = datetime.strptime(end.isoformat(), "%H:%M:%S")
    delta = end_dt - start_dt
    return delta.seconds // 60


@login_required
def proposal_export(request):
    if not request.user.is_superuser:
        return access_not_permitted(request)

    content_type = 'text/csv'
    response = HttpResponse(content_type=content_type)
    response['Content-Disposition'] = 'attachment; filename="proposal_export.csv"'

    domain = get_current_site(request).domain
    writer = unicodecsv.writer(response, quoting=unicodecsv.QUOTE_ALL)
    writer.writerow([
        'id',
        'proposal_type',
        'speaker',
        'title',
        'audience_level',
        'kind',
        'recording_release',
        'comment_count',
        'plus_one',
        'plus_zero',
        'minus_zero',
        'minus_one',
        'review_detail'
    ])

    proposals = ProposalBase.objects.all().select_subclasses().order_by('id')
    for proposal in proposals:
        writer.writerow([
            proposal.id,
            proposal._meta.module_name,
            proposal.speaker,
            proposal.title,
            proposal.audience_level,
            proposal.kind,
            proposal.recording_release,
            proposal.result.comment_count,
            proposal.result.plus_one,
            proposal.result.plus_zero,
            proposal.result.minus_zero,
            proposal.result.minus_one,
            'https://{0}{1}'.format(domain, reverse('review_detail',
                                                    args=[proposal.pk])),
        ])
    return response


def schedule_json(request):
    slots = Slot.objects.all().order_by("start")
    data = []
    for slot in slots:
        if slot.kind.label in ["talk", "tutorial", "plenary"] and slot.content and slot.content.proposal.kind.slug in ["talk", "tutorial"]:
            if hasattr(slot.content.proposal, "recording_release"):
                slot_data = {
                    "name": slot.content.title,
                    "room": ", ".join(room["name"] for room in slot.rooms.values()),
                    "start": datetime.combine(slot.day.date, slot.start).isoformat(),
                    "end": datetime.combine(slot.day.date, slot.end).isoformat(),
                    "duration": duration(slot.start, slot.end),
                    "authors": [s.name for s in slot.content.speakers()],
                    "released": slot.content.proposal.recording_release,
                    "license": "",
                    "contact": [s.email for s in slot.content.speakers()] if request.user.is_staff else ["redacted"],
                    "abstract": slot.content.abstract.raw,
                    "description": slot.content.description.raw,
                    "conf_key": slot.pk,
                    "conf_url": "https://%s%s" % (
                        Site.objects.get_current().domain,
                        reverse("schedule_presentation_detail", args=[slot.content.pk])
                    ),

                    "kind": slot.content.proposal.kind.slug,
                    "tags": "",
                }
        elif slot.kind.label == "lightning":
            slot_data = {
                "name": slot.content_override.raw if slot.content_override else "Lightning Talks",
                "room": ", ".join(room["name"] for room in slot.rooms.values()),
                "start": datetime.combine(slot.day.date, slot.start).isoformat(),
                "end": datetime.combine(slot.day.date, slot.end).isoformat(),
                "duration": duration(slot.start, slot.end),
                "authors": None,
                "released": True,
                "license": "",
                "contact": None,
                "abstract": "Lightning Talks",
                "description": "Lightning Talks",
                "conf_key": slot.pk,
                "conf_url": None,
                "kind": slot.kind.label,
                "tags": "",
            }
        else:
            continue
        data.append(slot_data)

    return HttpResponse(
        json.dumps(data, default=json_serializer),
        content_type="application/json"
    )
