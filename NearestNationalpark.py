import streamlit as st
import requests
import os
from dotenv import load_dotenv
load_dotenv()
import geopy.distance

#PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
PLACES_API_KEY = st.secrets["GOOGLE_PLACES_API_KEY"]

st.title("National Park Finder")

def get_place_suggestions(input_text):
    """Gets place suggestions from the Google Places Autocomplete API."""
    url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
    params = {
        "input": input_text,
        "types": "geocode",  # Restrict to geocodes (addresses)
        "key": PLACES_API_KEY,
    }
    response = requests.get(url, params=params)
    data = response.json()

    if data["status"] == "OK":
        predictions = data.get("predictions", [])
        suggestions = []
        for prediction in predictions:
            description = prediction["description"]
            place_id = prediction["place_id"]
            structured_formatting = prediction.get("structured_formatting", {})
            main_text = structured_formatting.get("main_text")
            secondary_text = structured_formatting.get("secondary_text")
            suggestions.append({
                "description": description,
                "place_id": place_id,
                "main_text": main_text,
                "secondary_text": secondary_text,
            })
        return suggestions
    else:
        st.error(f"Error: {data['status']}")
        return []

def get_location_coordinates(place_id):
    """Gets latitude and longitude for a selected place ID."""
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "geometry",  # Only need geometry for coordinates
        "key": PLACES_API_KEY,
    }
    response = requests.get(url, params=params)
    data = response.json()

    if data["status"] == "OK":
        result = data.get("result", {})
        geometry = result.get("geometry", {})
        location = geometry.get("location", {})
        lat = location.get("lat")
        lng = location.get("lng")
        return lat, lng
    else:
        st.error(f"Error getting coordinates: {data['status']}")
        return None, None

def get_nearest_national_parks(lat, lng, max_parks=5):
    """Finds the nearest national parks and their photos, with distances."""
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lng}",
        "radius": 50000,  # Adjust radius as needed
        "type": "park",
        "keyword": "national park",
        "key": PLACES_API_KEY,
    }
    response = requests.get(url, params=params)
    data = response.json()

    parks_data = []
    if data["status"] == "OK":
        results = data.get("results", [])
        for park in results[:max_parks]:
            place_id = park.get("place_id")
            name = park.get("name")
            location = park.get("geometry", {}).get("location", {})
            park_lat = location.get("lat")
            park_lng = location.get("lng")

            photos = get_place_photos(place_id)

            # Calculate distance
            origin = (lat, lng)
            destination = (park_lat, park_lng)
            distance = geopy.distance.geodesic(origin, destination).km

            parks_data.append({
                "name": name,
                "lat": park_lat,
                "lng": park_lng,
                "photos": photos,
                "distance": distance,
            })
    else:
        st.error(f"Error finding national parks: {data['status']}")

    return parks_data

def get_place_photos(place_id, max_photos=5):
    """Gets photo references for a place using the Place Details API."""
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "photos",  # Request only photos
        "key": PLACES_API_KEY,
    }
    response = requests.get(url, params=params)
    data = response.json()

    photo_urls = []
    if data["status"] == "OK":
        result = data.get("result", {})
        photos = result.get("photos", [])
        for photo in photos[:max_photos]:
            reference = photo.get("photo_reference")
            if reference:
                photo_urls.append(get_photo_url(reference))
    return photo_urls

def get_photo_url(photo_reference, max_width=400):
    """Constructs the URL for a photo."""
    return (
        f"https://maps.googleapis.com/maps/api/place/photo"
        f"?maxwidth={max_width}&photoreference={photo_reference}"
        f"&key={PLACES_API_KEY}"
    )

location_input = st.text_input("Enter a location:")

if location_input:
    suggestions = get_place_suggestions(location_input)

    if suggestions:
        formatted_suggestions = [
            f"{s['main_text']}, {s['secondary_text']}" if s.get('secondary_text') else s['main_text'] for s in suggestions
        ]

        selected_suggestion_index = st.selectbox("Select a location:", range(len(formatted_suggestions)), format_func=lambda i: formatted_suggestions[i])

        selected_place_id = suggestions[selected_suggestion_index]["place_id"]
        selected_description = suggestions[selected_suggestion_index]["description"]

        lat, lng = get_location_coordinates(selected_place_id)

        if lat and lng:
            st.write(f"Selected Location: {selected_description}")
            st.write(f"Latitude: {lat}, Longitude: {lng}")

            if st.button("Get Nearest National Parks"):
                with st.spinner("Finding national parks..."):
                    parks = get_nearest_national_parks(lat, lng)

                if parks:
                    for park in parks:
                        st.subheader(park["name"])
                        st.write(f"Distance: {park['distance']:.2f} km")
                        st.write(f"Latitude: {park['lat']}, Longitude: {park['lng']}")
                        map_data = {"lat": [park['lat']], "lon": [park['lng']]}
                        st.map(map_data, zoom=10)

                        if park["photos"]:
                            st.write("Park Photos:")
                            cols = st.columns(min(len(park["photos"]), 5))
                            for i, photo_url in enumerate(park["photos"][:5]):
                                cols[i].image(photo_url)
                        st.markdown("---")

                else:
                    st.write("No national parks found nearby.")