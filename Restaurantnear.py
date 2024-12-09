import streamlit as st
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
# For production, uncomment the line below and comment out the load_dotenv() and os.getenv line
# api_key = st.secrets["GOOGLE_PLACES_API_KEY"]
api_key = os.getenv("GOOGLE_PLACES_API_KEY")

# Predefined cuisine types
CUISINE_TYPES = [
    "American",
    "Italian",
    "Chinese",
    "Mexican",
    "Indian",
    "Japanese",
    "Thai",
    "Mediterranean",
    "French",
    "Korean"
]

# Specific cuisine type mapping
CUISINE_KEYWORDS = {
    "American": ["american"],
    "Italian": ["italian", "pizza", "pasta"],
    "Chinese": ["chinese", "dim sum"],
    "Mexican": ["mexican", "taco", "burrito"],
    "Indian": ["indian", "curry"],
    "Japanese": ["japanese", "sushi", "ramen"],
    "Thai": ["thai"],
    "Mediterranean": ["mediterranean", "greek", "lebanese"],
    "French": ["french", "bistro"],
    "Korean": ["korean", "bbq"]
}

# Function to filter cuisine types
def filter_cuisine_types(types):
    """
    Filter out irrelevant types and match with predefined cuisines
    """
    for cuisine, keywords in CUISINE_KEYWORDS.items():
        if any(keyword in type.lower() for type in types for keyword in keywords):
            return cuisine
    return None

# Function to get place suggestions
def get_place_suggestions(input_text):
    """
    Get place suggestions based on user input using Google Places Autocomplete API
    """
    url = f"https://maps.googleapis.com/maps/api/place/autocomplete/json?input={input_text}&types=(cities)&key={api_key}"
    try:
        response = requests.get(url)
        suggestions = response.json().get('predictions', [])
        return [prediction['description'] for prediction in suggestions]
    except Exception as e:
        st.error(f"Error fetching place suggestions: {e}")
        return []

# Function to get nearby restaurants
def get_nearby_restaurants(location, cuisine_filter=None, price_filter=None):
    """
    Find nearby restaurants using Google Places Nearby Search API with optional filters
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

        # Nearby search
        nearby_url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lng}&radius=1500&type=restaurant&rankby=prominence&key={api_key}"
        nearby_response = requests.get(nearby_url)
        restaurants = nearby_response.json().get('results', [])

        # Apply filters
        filtered_restaurants = restaurants

        # Cuisine Filter
        if cuisine_filter:
            filtered_restaurants = [
                rest for rest in filtered_restaurants
                if filter_cuisine_types(rest.get('types', [])) == cuisine_filter
            ]

        # Price Filter
        if price_filter:
            filtered_restaurants = [
                rest for rest in filtered_restaurants
                if rest.get('price_level') == price_filter
            ]

        # No restaurants found
        if not filtered_restaurants:
            st.warning("No restaurants found matching your criteria. Please try different filters.")

        return filtered_restaurants[:10]
    except Exception as e:
        st.error(f"Error finding restaurants: {e}")
        return []

# Function to get detailed restaurant information
def get_place_details(place_id):
    """
    Get comprehensive details for a specific restaurant
    """
    url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=name,formatted_address,url,website,editorial_summary,rating,user_ratings_total,reviews,types,price_level,photos&key={api_key}"
    try:
        response = requests.get(url)
        return response.json().get('result', {})
    except Exception as e:
        st.error(f"Error fetching place details: {e}")
        return {}

# Function to get restaurant photo
def get_place_photo(photo_reference, max_width=400):
    """
    Retrieve a restaurant photo
    """
    if not photo_reference:
        return None

    url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth={max_width}&photoreference={photo_reference}&key={api_key}"
    return url

# Function to create a photo carousel
def create_photo_carousel(photos, restaurant_name):
    """
    Display up to 5 photos in a side-by-side carousel format
    """
    if not photos:
        st.write("No photos available for this restaurant.")
        return

    # Display up to 5 photos using Streamlit columns
    num_photos = min(5, len(photos))
    columns = st.columns(num_photos)

    for i in range(num_photos):
        with columns[i]:
            photo_url = get_place_photo(photos[i]['photo_reference'])
            if photo_url:
                st.image(photo_url, caption=f"{restaurant_name} - Photo {i + 1}", use_column_width=True)

# Function to get compelling reviews
def get_compelling_reviews(reviews):
    """
    Filter and select compelling reviews
    """
    # First, try to get 5-star reviews
    five_star_reviews = [review for review in reviews if review.get('rating') == 5]

    # If no 5-star reviews, fall back to 4-star reviews
    if not five_star_reviews:
        five_star_reviews = [review for review in reviews if review.get('rating') == 4]

    # If still no reviews, return the first available review
    if not five_star_reviews and reviews:
        five_star_reviews = [reviews[0]]

    return five_star_reviews

# Streamlit App
def main():
    st.title("🍽️ Top Restaurants Finder")
    st.write("Discover the best dining spots near you!")

    # Location Input
    input_text = st.text_input("Enter a city or location:")

    # Sidebar Filters
    with st.sidebar:
        st.header("Filters")

        # Cuisine Type Filter
        cuisine_filter = st.selectbox(
            "Filter by Cuisine Type",
            ["All"] + CUISINE_TYPES
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

        # Find Restaurants Button
        if st.button("Find Top Restaurants"):
            # Prepare filters
            cuisine_filter = None if cuisine_filter == "All" else cuisine_filter
            price_filter = None if price_filter == "All" else {
                "$ (Inexpensive)": 1,
                "$$ (Moderate)": 2,
                "$$$ (Expensive)": 3,
                "$$$$ (Very Expensive)": 4
            }[price_filter]

            # Find Nearby Restaurants
            restaurants = get_nearby_restaurants(
                selected_location,
                cuisine_filter,
                price_filter
            )

            # Display Restaurants
            if restaurants:
                for i, restaurant in enumerate(restaurants, 1):
                    # Get detailed information
                    details = get_place_details(restaurant['place_id'])

                    # Create a card-like display for each restaurant
                    st.markdown(f"### {i}. {details.get('name', 'Unknown Restaurant')}")

                    # Photo Carousel Implementation
                    st.markdown("**Photo Gallery:**")
                    create_photo_carousel(details.get('photos', []), details.get('name', 'Unknown Restaurant'))

                    # Restaurant Details
                    col1, col2 = st.columns(2)

                    with col1:
                        st.write(f"**Location:** {details.get('formatted_address', 'N/A')}")
                        st.write(
                            f"**Rating:** {details.get('rating', 'N/A')} ⭐ ({details.get('user_ratings_total', 'N/A')} reviews)")

                    with col2:
                        # Google Maps Link
                        if 'url' in details:
                            st.markdown(f"[View on Google Maps]({details['url']})")

                        # Website Link
                        if 'website' in details:
                            st.markdown(f"[Official Website]({details['website']})")

                    # Cuisine Types
                    filtered_cuisine = filter_cuisine_types(details.get('types', []))
                    st.write(f"**Cuisine Type:** {filtered_cuisine or 'N/A'}")

                    # Compelling Reviews
                    if details.get('reviews'):
                        # Get compelling reviews
                        compelling_reviews = get_compelling_reviews(details['reviews'])

                        if compelling_reviews:
                            st.markdown("**Compelling Reviews:**")
                            for review in compelling_reviews:
                                # Extract name or use 'Anonymous'
                                reviewer_name = review.get('author_name', 'Anonymous')

                                st.markdown(f"> \"{review.get('text', 'No review text available')}\" - *{reviewer_name}*")

                    st.markdown("---")  # Separator between restaurants

# Run the app
if __name__ == "__main__":
    main()
