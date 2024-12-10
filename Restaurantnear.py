import streamlit as st
import requests
#import os
#from dotenv import load_dotenv

# Load environment variables
#load_dotenv()
#api_key = os.getenv("GOOGLE_PLACES_API_KEY")

api_key = st.secrets["GOOGLE_PLACES_API_KEY"]

# Updated list of place types
PLACE_TYPES = [
    'restaurant',
    'bar',
    'pub',
    'cafe',
    'lodging'
]


def get_place_suggestions(input_text):
    """
    Get place suggestions based on user input using Google Places Autocomplete API
    """
    url = f"https://maps.googleapis.com/maps/api/place/autocomplete/json?input={input_text}&types=geocode&key={api_key}"
    try:
        response = requests.get(url)
        suggestions = response.json().get('predictions', [])
        return [prediction['description'] for prediction in suggestions]
    except Exception as e:
        st.error(f"Error fetching place suggestions: {e}")
        return []


def get_nearby_places(location, type_filter=None, price_filter=None):
    """
    Find nearby places using Google Places Nearby Search API with optional filters
    """
    # First, get the geocoding for the location
    geocoding_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={location}&key={api_key}"
    try:
        geocoding_response = requests.get(geocoding_url)
        location_data = geocoding_response.json()

        if location_data['status'] != 'OK':
            st.error("Could not find location coordinates. Please check the location and try again.")
            return []

        # Extract latitude and longitude
        location = location_data['results'][0]['geometry']['location']
        lat, lng = location['lat'], location['lng']

        # Prepare type filter if specified
        type_filter = type_filter if type_filter else "restaurant"

        # Updated nearby search with place type and price level
        nearby_url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lng}&radius=1500&type={type_filter}&key={api_key}"

        # Add price level if specified
        # Price levels match the Google Places API standard: 0=Free, 1=Inexpensive, 2=Moderate, 3=Expensive, 4=Very Expensive
        if price_filter is not None:
            nearby_url += f"&minprice={price_filter}&maxprice={price_filter}"

        nearby_response = requests.get(nearby_url)
        places = nearby_response.json().get('results', [])

        # No places found
        if not places:
            st.warning("No places found matching your criteria. Please try different filters.")

        return places[:10]
    except Exception as e:
        st.error(f"Error finding places: {e}")
        return []


def get_place_details(place_id):
    """
    Get comprehensive details for a specific place with multiple photo references
    """
    url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=name,formatted_address,url,website,editorial_summary,rating,user_ratings_total,reviews,types,price_level,photos&key={api_key}"
    try:
        response = requests.get(url)
        return response.json().get('result', {})
    except Exception as e:
        st.error(f"Error fetching place details: {e}")
        return {}


def get_place_photo(photo_reference, max_width=400):
    """
    Retrieve a place photo
    """
    if not photo_reference:
        return None

    url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth={max_width}&photoreference={photo_reference}&key={api_key}"
    return url


def get_price_level_description(price_level):
    """
    Convert numeric price level to descriptive string
    """
    price_levels = {
        0: '$ (Free)',
        1: '$ (Inexpensive)',
        2: '$$ (Moderate)',
        3: '$$$ (Expensive)',
        4: '$$$$ (Very Expensive)'
    }
    return price_levels.get(price_level, 'N/A')


def get_compelling_reviews(reviews):
    """
    Select one compelling review with at least 4 characters
    """
    # Filter reviews with at least 4 characters
    valid_reviews = [
        review for review in reviews
        if len(review.get('text', '').strip()) >= 4
    ]

    # Sort reviews by rating in descending order
    valid_reviews.sort(key=lambda x: x.get('rating', 0), reverse=True)

    # Return the top review if available
    return [valid_reviews[0]] if valid_reviews else []


def main():
    st.title("🍽️ Top Places Finder")
    st.write("Discover the best spots near you!")

    # Location Input
    input_text = st.text_input("Enter a city or location:")

    # Sidebar Filters
    with st.sidebar:
        st.header("Filters")

        # Place Type Filter
        type_filter = st.selectbox(
            "Filter by Type of Place",
            ["All"] + sorted(PLACE_TYPES)
        )

        # Price Range Filter
        price_filter = st.selectbox(
            "Filter by Price Range",
            [
                "All",
                "$ (Inexpensive)",
                "$$ (Moderate)",
                "$$$ (Expensive)",
                "$$$$ (Very Expensive)"
            ]
        )

    # Get Place Suggestions
    if input_text:
        suggestions = get_place_suggestions(input_text)

        if not suggestions:
            st.error(f"No locations found for '{input_text}'. Please try a different location.")
            return

        # Location Selection
        selected_location = st.selectbox("Select a specific location:", suggestions)

        # Find Places Button
        if st.button("Find Top Places"):
            # Prepare filters
            type_filter = None if type_filter == "All" else type_filter
            price_filter = None if price_filter == "All" else {
                "$ (Inexpensive)": 1,
                "$$ (Moderate)": 2,
                "$$$ (Expensive)": 3,
                "$$$$ (Very Expensive)": 4
            }[price_filter]

            # Find Nearby Places
            places = get_nearby_places(
                selected_location,
                type_filter,
                price_filter
            )

            # Display Places
            if places:
                for i, place in enumerate(places, 1):
                    # Get detailed information
                    details = get_place_details(place['place_id'])

                    # Create a card-like display for each place
                    st.markdown(f"### {i}. {details.get('name', 'Unknown Place')}")

                    # Display Photos in Carousel/Grid
                    if details.get('photos'):
                        # Select up to 5 photos
                        photos = details['photos'][:5]

                        # Create a grid of photo columns
                        cols = st.columns(len(photos))

                        for j, photo in enumerate(photos):
                            photo_url = get_place_photo(photo['photo_reference'])
                            if photo_url:
                                cols[j].image(photo_url, use_container_width=True)

                    # Place Details
                    col1, col2 = st.columns(2)

                    with col1:
                        st.write(f"**Location:** {details.get('formatted_address', 'N/A')}")
                        st.write(
                            f"**Rating:** {details.get('rating', 'N/A')} ⭐ ({details.get('user_ratings_total', 'N/A')} reviews)")

                    with col2:
                        # Price Level
                        price_level = details.get('price_level')
                        if price_level is not None:
                            st.write(f"**Price Range:** {get_price_level_description(price_level)}")

                        # Google Maps Link
                        if 'url' in details:
                            st.markdown(f"[Get Directions]({details['url']})")

                        # Website Link
                        # if 'website' in details:
                        #     st.markdown(f"[Official Website]({details['website']})")

                    # Place Types - display all types
                    #st.write(f"**Place Types:** {', '.join(details.get('types', ['N/A']))}")

                    # Compelling Reviews
                    if details.get('reviews'):
                        # Get one compelling review
                        compelling_reviews = get_compelling_reviews(details['reviews'])

                        if compelling_reviews:
                            st.markdown("**Compelling Review:**")
                            review = compelling_reviews[0]
                            # Extract name or use 'Anonymous'
                            reviewer_name = review.get('author_name', 'Anonymous')

                            st.markdown(f"> \"{review.get('text', 'No review text available')}\" - *{reviewer_name}*")

                    st.markdown("---")  # Separator between places


# Run the app
if __name__ == "__main__":
    main()