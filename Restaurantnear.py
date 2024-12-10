import streamlit as st
#import requests
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


# (Keep all previous functions the same: get_place_suggestions, get_nearby_places, get_place_details,
#  get_place_photo, get_price_level_description, get_compelling_reviews)
# ... (previous functions remain unchanged)

def main():
    st.title("🍽️ Top Places Finder")
    st.write("Discover the best spots near you!")

    # Location Input
    input_text = st.text_input("Enter a city or location:")

    # Filters directly below location input
    col1, col2 = st.columns(2)

    with col1:
        # Place Type Filter
        type_filter = st.selectbox(
            "Filter by Type of Place",
            ["All"] + sorted(PLACE_TYPES)
        )

    with col2:
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
        if st.button("Find Top Dining Places"):
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
                            st.markdown(f"[View on Google Maps]({details['url']})")

                        # Website Link
                        if 'website' in details:
                            st.markdown(f"[Official Website]({details['website']})")

                    # Place Types - display all types
                    st.write(f"**Place Types:** {', '.join(details.get('types', ['N/A']))}")

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