import streamlit as st
import requests
#import os
#from dotenv import load_dotenv
import functools
import time

# Load environment variables
#load_dotenv()
#api_key = os.getenv("GOOGLE_PLACES_API_KEY")

#for prod
pi_key = st.secrets("GOOGLE_PLACES_API_KEY")

# Enhanced Cuisine Types
CUISINE_TYPES = [
    "American", "Italian", "Chinese", "Mexican", "Indian", "Japanese", "Thai",
    "Mediterranean", "French", "Korean", "Spanish", "Vietnamese", "Greek",
    "Middle Eastern", "Brazilian", "Caribbean", "African", "German"
]

# Enhanced Cuisine Type Mapping
CUISINE_KEYWORDS = {
    "American": ["american", "burger", "grill"],
    "Italian": ["italian", "pizza", "pasta", "trattoria"],
    "Chinese": ["chinese", "dim sum", "cantonese", "sichuan"],
    "Mexican": ["mexican", "taco", "burrito", "tex-mex"],
    "Indian": ["indian", "curry", "tandoori", "north indian", "south indian"],
    "Japanese": ["japanese", "sushi", "ramen", "izakaya"],
    "Thai": ["thai", "pad thai", "thai cuisine"],
    "Mediterranean": ["mediterranean", "greek", "lebanese", "israeli"],
    "French": ["french", "bistro", "patisserie", "brasserie"],
    "Korean": ["korean", "bbq", "korean cuisine"],
    "Spanish": ["spanish", "tapas"],
    "Vietnamese": ["vietnamese", "pho"],
    "Greek": ["greek", "gyro", "souvlaki"],
    "Middle Eastern": ["middle eastern", "falafel", "kebab"],
    "Brazilian": ["brazilian", "churrascaria"],
    "Caribbean": ["caribbean", "jamaican"],
    "African": ["african", "ethiopian"],
    "German": ["german", "schnitzel"]
}


# Implement caching decorator
def cache_api_call(timeout=3600):  # 1-hour cache
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create a cache key based on function name and arguments
            cache_key = f"{func.__name__}_{hash(str(args) + str(kwargs))}"

            # Check if cached result exists and is still valid
            if hasattr(wrapper, 'cached_result'):
                cached_time, result = wrapper.cached_result
                if time.time() - cached_time < timeout:
                    return result

            # If no valid cache, call the function
            result = func(*args, **kwargs)

            # Store the result with current timestamp
            wrapper.cached_result = (time.time(), result)

            return result

        return wrapper

    return decorator


# Comprehensive error handling wrapper
def handle_api_errors(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.exceptions.RequestException as e:
            st.error(f"Network Error: {e}")
            return None
        except ValueError as e:
            st.error(f"Data Processing Error: {e}")
            return None
        except Exception as e:
            st.error(f"Unexpected Error: {e}")
            return None

    return wrapper


@handle_api_errors
@cache_api_call()
def get_place_suggestions(input_text):
    """Enhanced place suggestions with more robust error handling"""
    url = f"https://maps.googleapis.com/maps/api/place/autocomplete/json?input={input_text}&types=(cities)&key={api_key}"
    response = requests.get(url)
    response.raise_for_status()  # Raise error for bad responses
    suggestions = response.json().get('predictions', [])

    # More robust suggestion handling
    if not suggestions:
        st.warning(f"No locations found for '{input_text}'. Try a different location.")

    return [prediction['description'] for prediction in suggestions]


@handle_api_errors
@cache_api_call()
def get_nearby_restaurants(location, cuisine_filter=None, price_filter=None,
                           open_now=False, additional_filters=None):
    """Enhanced restaurant search with more filtering options"""
    # Geocoding
    geocoding_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={location}&key={api_key}"
    geocoding_response = requests.get(geocoding_url)
    location_data = geocoding_response.json()

    if location_data['status'] != 'OK':
        st.error("Could not find location coordinates.")
        return []

    location = location_data['results'][0]['geometry']['location']
    lat, lng = location['lat'], location['lng']

    # Construct nearby search URL with additional parameters
    params = {
        "location": f"{lat},{lng}",
        "radius": 1500,
        "type": "restaurant",
        "key": api_key
    }

    if open_now:
        params["opennow"] = True

    nearby_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    nearby_response = requests.get(nearby_url, params=params)
    restaurants = nearby_response.json().get('results', [])

    # Apply filters
    filtered_restaurants = restaurants

    # Cuisine Filter
    if cuisine_filter:
        filtered_restaurants = [
            rest for rest in filtered_restaurants
            if any(keyword in str(rest.get('types', '')).lower()
                   for keyword in CUISINE_KEYWORDS.get(cuisine_filter, []))
        ]

    # Price Filter
    if price_filter:
        filtered_restaurants = [
            rest for rest in filtered_restaurants
            if rest.get('price_level') == price_filter
        ]

    # Additional custom filters
    if additional_filters:
        for filter_func in additional_filters:
            filtered_restaurants = list(filter(filter_func, filtered_restaurants))

    return filtered_restaurants


@handle_api_errors
@cache_api_call()
def get_place_details(place_id):
    """Enhanced place details with more comprehensive information"""
    url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=name,formatted_address,url,website,editorial_summary,rating,user_ratings_total,reviews,types,price_level,photos&key={api_key}"
    response = requests.get(url)
    return response.json().get('result', {})


@handle_api_errors
def get_place_photos(details, max_width=400, max_photos=5):
    """Retrieve multiple restaurant photos"""
    photos = details.get('photos', [])
    photo_urls = []

    for photo in photos[:max_photos]:
        url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth={max_width}&photoreference={photo['photo_reference']}&key={api_key}"
        photo_urls.append(url)

    return photo_urls


def filter_cuisine_types(types):
    """Enhanced cuisine type filtering"""
    for cuisine, keywords in CUISINE_KEYWORDS.items():
        if any(keyword in type.lower() for type in types for keyword in keywords):
            return cuisine
    return None


def get_best_review(reviews):
    """Get the top review, preferably 5-star"""
    if not reviews:
        return None

    # Sort reviews by rating in descending order
    sorted_reviews = sorted(reviews, key=lambda x: x.get('rating', 0), reverse=True)
    return sorted_reviews[0]


def main():
    st.title("🍽️ Advanced Restaurant Finder")
    st.write("Discover the best dining spots with advanced search!")

    # Location Input
    input_text = st.text_input("Enter a city or location:")

    # Sidebar Filters
    with st.sidebar:
        st.header("Advanced Filters")

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

        # Open Now Filter
        open_now = st.checkbox("Open Now")

        # Pagination
        results_per_page = st.slider("Restaurants per page", 5, 20, 10)

    # Location Suggestions
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
                price_filter,
                open_now
            )

            # Pagination
            total_restaurants = len(restaurants)
            total_pages = (total_restaurants + results_per_page - 1) // results_per_page
            current_page = st.number_input("Page", min_value=1, max_value=total_pages, value=1)

            start_idx = (current_page - 1) * results_per_page
            end_idx = start_idx + results_per_page
            page_restaurants = restaurants[start_idx:end_idx]

            # Display Restaurants
            if page_restaurants:
                for i, restaurant in enumerate(page_restaurants, 1):
                    # Get detailed information
                    details = get_place_details(restaurant['place_id'])

                    # Create a card-like display for each restaurant
                    st.markdown(f"### {start_idx + i}. {details.get('name', 'Unknown Restaurant')}")

                    # Photo Carousel
                    photo_urls = get_place_photos(details)
                    if photo_urls:
                        st.image(photo_urls, width=400, use_column_width=False)

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

                    # Single Top Review
                    if details.get('reviews'):
                        top_review = get_best_review(details['reviews'])
                        if top_review:
                            st.markdown("**Top Review:**")
                            reviewer_name = top_review.get('author_name', 'Anonymous')
                            st.markdown(
                                f"> \"{top_review.get('text', 'No review text available')}\" - *{reviewer_name}*")

                    st.markdown("---")  # Separator between restaurants

                # Pagination Controls
                col1, col2, col3 = st.columns(3)
                with col1:
                    if current_page > 1:
                        st.button("Previous Page")
                with col3:
                    if current_page < total_pages:
                        st.button("Next Page")

            else:
                st.warning("No restaurants found matching your criteria.")


# Run the app
if __name__ == "__main__":
    main()