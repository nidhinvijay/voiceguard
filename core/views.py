# core/views.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.http import JsonResponse
from django.conf import settings

from django.views.decorators.http import require_GET, require_POST
from django.db.models import Q
from django.db import transaction

from .forms import SignUpForm
from .models import CustomUser, Contact
from django.utils.dateparse import parse_datetime
from django.db.models import Avg
from .models import CallRecord
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
# --- Existing Twilio imports (token view stays for now; we'll swap to Voice later) ---
import os
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant  # will be changed to Voice grant later
# from twilio.rest import Client  # not needed right now

# --------------------------
# Helpers (phone normalization)
# --------------------------
import re

PHONE_REGEX = re.compile(r'^\+91\d{10}$')

def _normalize_phone(value: str) -> str:
    """
    Remove spaces/dashes. If user enters plain 10 digits, assume India and prepend +91.
    Otherwise expect +91XXXXXXXXXX.
    """
    if not value:
        return value
    v = re.sub(r'[\s\-]', '', value)
    if re.fullmatch(r'\d{10}', v):
        v = f'+91{v}'
    return v


# --------------------------
# Auth & Home
# --------------------------

@login_required
def index(request):
    # Call screen (existing)
    return render(request, 'core/index.html')


def signup_view(request):
    # Registration: username + password + display_name + phone (+91 only) + optional email
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Option A: redirect to login page (simple & explicit)
            return redirect('login')
            # Option B: auto-login
            # login(request, user)
            # return redirect('index')
    else:
        form = SignUpForm()
    return render(request, 'core/signup.html', {'form': form})


@login_required
def get_twilio_token(request):
    import os
    from twilio.jwt.access_token import AccessToken
    from twilio.jwt.access_token.grants import VoiceGrant

    user = request.user
    # Use phone number as the Twilio Client identity
    identity = getattr(user, "phone_number", None) or user.username

    account_sid = os.environ['TWILIO_ACCOUNT_SID']
    key_sid = os.environ['TWILIO_API_KEY_SID']
    key_secret = os.environ['TWILIO_API_KEY_SECRET']
    app_sid = os.environ['TWILIO_VOICE_TWIML_APP_SID']

    token = AccessToken(account_sid, key_sid, key_secret, identity=identity)
    voice_grant = VoiceGrant(outgoing_application_sid=app_sid, incoming_allow=True)
    token.add_grant(voice_grant)

    return JsonResponse({'ok': True, 'token': token.to_jwt(), 'identity': identity})


# --------------------------
# Directory (page + search)
# --------------------------

@login_required
def directory_page(request):
    """
    Renders the directory/search UI.
    Results are fetched client-side from /directory/search via fetch().
    """
    return render(request, 'core/directory.html')


@login_required
@require_GET
def directory_search(request):
    """
    Results = Contacts (accepted, name OR phone contains query)
              ∪ Directory (exact +91XXXXXXXXXX phone match across all users, excluding self).
    No discoverability toggle: exact phone match is always allowed.
    """
    me = request.user
    q = (request.GET.get('q') or '').strip()

    contacts = []
    directory = []

    if not q:
        return JsonResponse({'contacts': [], 'directory': []})

    # Contacts search (accepted only) — name or phone contains query
    contacts_qs = CustomUser.objects.filter(
        contact_of__owner=me,
        contact_of__status=Contact.Status.ACCEPTED
    ).filter(
        Q(display_name__icontains=q) | Q(phone_number__icontains=q)
    ).distinct()

    for u in contacts_qs[:25]:
        # relation: accepted (we know these are accepted results)
        contacts.append({
            'display_name': u.display_name,
            'phone': u.phone_number,
            'lifetime_avg': getattr(u, 'lifetime_toxicity_avg', None),
            'relation': 'accepted',
        })

    # Directory search — only if q is an exact +91… number
    normalized = _normalize_phone(q)
    if PHONE_REGEX.fullmatch(normalized):
        dir_user = CustomUser.objects.filter(phone_number=normalized).exclude(pk=me.pk).first()
        if dir_user:
            # Determine my relation to this user (if any)
            edge = Contact.objects.filter(owner=me, contact=dir_user).first()
            relation = edge.status if edge else None
            directory.append({
                'display_name': dir_user.display_name,
                'phone': dir_user.phone_number,
                'lifetime_avg': getattr(dir_user, 'lifetime_toxicity_avg', None),
                'relation': relation,  # None | requested | accepted | blocked
            })

    return JsonResponse({'contacts': contacts, 'directory': directory})


# --------------------------
# Contacts (request / accept / block / list / pending)
# --------------------------

def _get_user_by_phone_strict(phone: str):
    # Strict exact phone match (+91XXXXXXXXXX)
    phone = _normalize_phone(phone)
    if not PHONE_REGEX.fullmatch(phone or ''):
        return None
    return CustomUser.objects.filter(phone_number=phone).first()


@login_required
@require_POST
def contacts_request(request):
    """
    Send a contact request to an exact +91XXXXXXXXXX user.
    - Cannot request self
    - If already accepted or requested -> idempotent success
    - If blocked by either side -> reject
    """
    me = request.user
    phone = (request.POST.get('phone') or '').strip()
    target = _get_user_by_phone_strict(phone)
    if not target:
        return JsonResponse({'ok': False, 'error': 'User not found'}, status=404)
    if target.pk == me.pk:
        return JsonResponse({'ok': False, 'error': 'Cannot add yourself'}, status=400)

    # Block checks
    blocked = Contact.objects.filter(owner=me, contact=target, status=Contact.Status.BLOCKED).exists() \
        or Contact.objects.filter(owner=target, contact=me, status=Contact.Status.BLOCKED).exists()
    if blocked:
        return JsonResponse({'ok': False, 'error': 'Contact is blocked'}, status=403)

    with transaction.atomic():
        me_edge, created = Contact.objects.get_or_create(
            owner=me, contact=target,
            defaults={'status': Contact.Status.REQUESTED}
        )
        if me_edge.status == Contact.Status.BLOCKED:
            return JsonResponse({'ok': False, 'error': 'You blocked this user'}, status=403)
        if me_edge.status == Contact.Status.ACCEPTED:
            return JsonResponse({'ok': True, 'message': 'Already contacts', 'status': 'accepted'})
        if me_edge.status == Contact.Status.REQUESTED and not created:
            return JsonResponse({'ok': True, 'message': 'Request already sent', 'status': 'requested'})

        me_edge.status = Contact.Status.REQUESTED
        me_edge.save(update_fields=['status'])

    return JsonResponse({'ok': True, 'message': 'Request sent', 'status': 'requested'})


@login_required
@require_POST
def contacts_accept(request):
    """
    Accept an incoming request from phone.
    - Requires existing edge (other -> me) with status=requested
    - Sets both directions to accepted (creates my edge if missing)
    - Cannot accept if either side blocked
    """
    me = request.user
    phone = (request.POST.get('phone') or '').strip()
    other = _get_user_by_phone_strict(phone)
    if not other:
        return JsonResponse({'ok': False, 'error': 'User not found'}, status=404)
    if other.pk == me.pk:
        return JsonResponse({'ok': False, 'error': 'Invalid'}, status=400)

    blocked = Contact.objects.filter(owner=me, contact=other, status=Contact.Status.BLOCKED).exists() \
        or Contact.objects.filter(owner=other, contact=me, status=Contact.Status.BLOCKED).exists()
    if blocked:
        return JsonResponse({'ok': False, 'error': 'Blocked'}, status=403)

    with transaction.atomic():
        incoming = Contact.objects.filter(owner=other, contact=me).first()
        if not incoming or incoming.status != Contact.Status.REQUESTED:
            return JsonResponse({'ok': False, 'error': 'No pending request from this user'}, status=400)

        # Accept both sides
        incoming.status = Contact.Status.ACCEPTED
        incoming.save(update_fields=['status'])

        mine, created = Contact.objects.get_or_create(
            owner=me, contact=other,
            defaults={'status': Contact.Status.ACCEPTED}
        )
        if not created and mine.status != Contact.Status.ACCEPTED:
            mine.status = Contact.Status.ACCEPTED
            mine.save(update_fields=['status'])

    return JsonResponse({'ok': True, 'message': 'Contact accepted', 'status': 'accepted'})


@login_required
@require_POST
def contacts_block(request):
    """
    Block a user by phone:
    - My edge -> BLOCKED (create if missing)
    - Remove their non-blocked edge so they no longer see me as contact
    """
    me = request.user
    phone = (request.POST.get('phone') or '').strip()
    other = _get_user_by_phone_strict(phone)
    if not other:
        return JsonResponse({'ok': False, 'error': 'User not found'}, status=404)
    if other.pk == me.pk:
        return JsonResponse({'ok': False, 'error': 'Invalid'}, status=400)

    with transaction.atomic():
        mine, created = Contact.objects.get_or_create(
            owner=me, contact=other,
            defaults={'status': Contact.Status.BLOCKED}
        )
        if mine.status != Contact.Status.BLOCKED:
            mine.status = Contact.Status.BLOCKED
            mine.save(update_fields=['status'])

        # Remove their edge if it exists and is not blocked
        Contact.objects.filter(owner=other, contact=me).exclude(status=Contact.Status.BLOCKED).delete()

    return JsonResponse({'ok': True, 'message': 'User blocked', 'status': 'blocked'})


@login_required
@require_GET
def contacts_pending(request):
    """
    List incoming pending requests to me:
    edges where (owner -> me) has status=requested
    """
    me = request.user
    incoming = Contact.objects.filter(
        contact=me, status=Contact.Status.REQUESTED
    ).select_related('owner')[:50]

    data = [{
        'from_display_name': edge.owner.display_name,
        'from_phone': edge.owner.phone_number
    } for edge in incoming]

    return JsonResponse({'ok': True, 'incoming': data})


@login_required
@require_GET
def contacts_list(request):
    """
    My accepted contacts (owner=me, status=accepted)
    """
    me = request.user
    accepted = Contact.objects.filter(owner=me, status=Contact.Status.ACCEPTED).select_related('contact')[:200]
    data = [{
        'display_name': e.contact.display_name,
        'phone': e.contact.phone_number
    } for e in accepted]
    return JsonResponse({'ok': True, 'contacts': data})


def _update_lifetime_avg(user):
    """
    Recompute and cache the user's lifetime average toxicity.
    Simple full-average; you can switch to 'last N calls' if desired.
    """
    agg = CallRecord.objects.filter(caller=user).aggregate(a=Avg('avg_toxicity'))
    val = agg['a']
    user.lifetime_toxicity_avg = val
    user.save(update_fields=['lifetime_toxicity_avg'])
    return val

@login_required
@require_POST
def calls_finish(request):
    """
    Client posts the final average toxicity at the end of a call.
    Payload: peer_phone, started_at (ISO), ended_at (ISO), avg_toxicity [0..1], lang (optional)
    We create CallRecord(caller=request.user, receiver=peer) and update caller's lifetime cache.
    """
    me = request.user
    peer_phone = (request.POST.get('peer_phone') or '').strip()
    started_at_str = (request.POST.get('started_at') or '').strip()
    ended_at_str = (request.POST.get('ended_at') or '').strip()
    avg_toxicity_str = (request.POST.get('avg_toxicity') or '').strip()
    lang = (request.POST.get('lang') or '').strip() or None

    # Validate
    peer = CustomUser.objects.filter(phone_number=peer_phone).exclude(pk=me.pk).first()
    if not peer:
        return JsonResponse({'ok': False, 'error': 'Peer not found'}, status=404)

    started_at = parse_datetime(started_at_str)
    ended_at = parse_datetime(ended_at_str)
    try:
        avg_toxicity = float(avg_toxicity_str)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Invalid toxicity'}, status=400)

    if not started_at or not ended_at or avg_toxicity < 0 or avg_toxicity > 1:
        return JsonResponse({'ok': False, 'error': 'Bad payload'}, status=400)

    duration = int((ended_at - started_at).total_seconds())
    if duration < 0:
        duration = None

    rec = CallRecord.objects.create(
        caller=me,
        receiver=peer,
        started_at=started_at,
        ended_at=ended_at,
        avg_toxicity=avg_toxicity,
        duration_sec=duration,
        lang=lang
    )
    lifetime = _update_lifetime_avg(me)
    return JsonResponse({'ok': True, 'id': rec.id, 'lifetime_avg': lifetime})

@login_required
@require_GET
def calls_history(request):
    """
    Return my recent calls (as caller) for per-call view in my account.
    """
    me = request.user
    qs = CallRecord.objects.filter(caller=me).select_related('receiver').order_by('-started_at')[:50]
    data = [{
        'receiver_display_name': c.receiver.display_name,
        'receiver_phone': c.receiver.phone_number,
        'started_at': c.started_at.isoformat(),
        'ended_at': c.ended_at.isoformat(),
        'duration_sec': c.duration_sec,
        'avg_toxicity': c.avg_toxicity,
    } for c in qs]
    return JsonResponse({'ok': True, 'calls': data})

@login_required
@require_GET
def lifetime_avg(request):
    """
    Return lifetime avg for a given phone (used for incoming badge).
    Query param: phone=+91XXXXXXXXXX
    """
    phone = (request.GET.get('phone') or '').strip()
    u = CustomUser.objects.filter(phone_number=phone).first()
    if not u:
        return JsonResponse({'ok': False, 'error': 'Not found'}, status=404)
    return JsonResponse({'ok': True, 'lifetime_avg': u.lifetime_toxicity_avg})


# core/views.py  (append)

@login_required
def history_page(request):
    """
    Render the Recent Calls page. The table is populated via fetch(/calls/history).
    """
    return render(request, 'core/history.html')


@csrf_exempt
def twiml_voice(request):
    """
    This is the Voice URL for your TwiML App.
    Twilio will POST here when your browser starts an outbound call using Device.connect({ params: { To } }).
    We respond with TwiML that dials the other browser client by identity.
    """
    to_identity = request.POST.get('To', '').strip()
    # Dial <Client><Identity> callee_identity </Identity></Client>
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Dial>
    <Client>
      <Identity>{to_identity}</Identity>
    </Client>
  </Dial>
</Response>"""
    return HttpResponse(twiml, content_type='text/xml')