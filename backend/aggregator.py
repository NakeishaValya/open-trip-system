from fastapi import APIRouter, HTTPException
import os
from typing import List, Dict, Any
import httpx

router = APIRouter(prefix="/aggregator", tags=["Aggregator"])

OPEN_TRIP_URL = os.getenv("OPEN_TRIP_URL", "http://localhost:8002")
TRAVEL_PLANNER_URL = os.getenv("TRAVEL_PLANNER_URL", "http://localhost:8003")


@router.get('/bookings/{trip_id}')
async def aggregate_booking_passengers(trip_id: str, plan_id: str = None):
    """Aggregate participants from booking service and inject pickupPoint from travel planner.

    Steps:
    - GET booking participants from Service1 (open trip)
    - Extract unique trip_pickup_id values
    - GET pickup points from Service2 (travel planner) either by plan_id or by ids batch
    - Map trip_pickup_id -> lokasi_jemput and inject as `pickupPoint`
    - Return normalized passenger array
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1) fetch bookings/participants from open-trip service
        booking_url = f"{OPEN_TRIP_URL}/api/opentrip/bookings/by_trip/{trip_id}"
        resp = await client.get(booking_url)
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Booking/trip not found")
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Upstream booking service error: {resp.status_code}")

        bookings = resp.json() or []

        # collect participant objects
        participants = []
        for b in bookings:
            p = b.get('passenger') or b.get('participant') or b.get('passenger')
            # try multiple shapes
            if p:
                # ensure participant_id if present at booking root
                if not p.get('participant_id') and b.get('participant_id'):
                    p['participant_id'] = b.get('participant_id')
                participants.append(p)

        if not participants:
            return {"participants": []}

        # 2) determine pickup ids to fetch
        pickup_map: Dict[str, str] = {}

        # prefer plan_id param, then try to read from booking payload
        effective_plan_id = plan_id or bookings[0].get('plan_id')

        if effective_plan_id:
            pickups_url = f"{TRAVEL_PLANNER_URL}/api/trip-pickup-points"
            r = await client.get(pickups_url, params={"plan_id": effective_plan_id})
            if r.status_code == 200:
                try:
                    pickups = r.json() or []
                    pickup_map = {str(p.get('trip_pickup_id')): p.get('lokasi_jemput') for p in pickups}
                except Exception:
                    pickup_map = {}
        else:
            # gather unique ids from participants
            unique_ids = {str(p.get('trip_pickup_id')) for p in participants if p.get('trip_pickup_id')}
            if unique_ids:
                # call travel planner batch lookup (ids comma separated)
                pickups_url = f"{TRAVEL_PLANNER_URL}/api/trip-pickup-points"
                params = {"ids": ",".join(unique_ids)}
                r = await client.get(pickups_url, params=params)
                if r.status_code == 200:
                    try:
                        pickups = r.json() or []
                        pickup_map = {str(p.get('trip_pickup_id')): p.get('lokasi_jemput') for p in pickups}
                    except Exception:
                        pickup_map = {}

        # 3) normalize participants into required return structure
        def normalize(p: Dict[str, Any]) -> Dict[str, Any]:
            first = p.get('first_name') or p.get('name') or ""
            last = p.get('last_name') or ""
            customer_name = (first + ' ' + last).strip() if (first or last) else (p.get('customerName') or p.get('name') or '')

            trip_pickup_id = p.get('trip_pickup_id') or p.get('pick_up_point') or p.get('pick_up_point_id')
            # if pick_up_point already contains text, use it directly
            pickup_point = None
            if trip_pickup_id and isinstance(trip_pickup_id, str) and len(trip_pickup_id) == 36:
                pickup_point = pickup_map.get(trip_pickup_id)
            else:
                # maybe already a string lokasi
                pickup_point = p.get('pick_up_point') or p.get('pick_up_point_text')

            return {
                "participant_id": p.get('participant_id') or p.get('participantId') or None,
                "customerName": customer_name or None,
                "phoneNumber": p.get('phone_number') or p.get('phoneNumber') or p.get('contact') or None,
                "gender": p.get('gender') or None,
                "nationality": p.get('nationality') or None,
                "dateOfBirth": p.get('date_of_birth') or p.get('dateOfBirth') or None,
                "pickupPoint": pickup_point or None,
                "notes": p.get('notes') or ""
            }

        unified = [normalize(p) for p in participants]
        return {"participants": unified}
