import streamlit as st
import requests
import google.generativeai as genai
import os
from dotenv import load_dotenv
import time
import json
import re
import random
import re
from typing import List, Dict, Any, Optional

# Load environment variables and configure API
#load_dotenv()

# Configure Streamlit page
st.set_page_config(
    page_title="AI Restaurant Finder",
    page_icon="🍽️",
    layout="centered"
)

# Get API keys from environment variables
# GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GOOGLE_PLACES_API_KEY = st.secrets["GOOGLE_PLACES_API_KEY"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]


def initialize_session_state():
    """Initialize or reset session state variables for the application flow."""
    default_state = {
        'step': 1,
        'total_steps': 6,  # Updated to include AI recommendation steps
        'location': None,
        'location_data': None,
        'establishment_type': None,
        'distance': None,
        'restaurants_data': None,
        'max_results': 60,  # Maximum restaurants to fetch
        'current_question': 0,
        'questions': None,
        'answers': {},
        'final_recommendation': None
    }

    for key, value in default_state.items():
        if key not in st.session_state:
            st.session_state[key] = value


class RestaurantFinder:
    """Handles all Google Places API interactions for restaurant discovery."""

    def __init__(self):
        """Initialize the RestaurantFinder with API key validation."""
        self.places_api_key = GOOGLE_PLACES_API_KEY
        if not self.places_api_key:
            st.error("Google Places API key not found in environment variables.")
            raise ValueError("Missing API key")

    def get_place_suggestions(self, input_text: str) -> List[str]:
        """Get location suggestions using Google Places Autocomplete."""
        try:
            url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
            params = {
                "input": input_text,
                "types": "geocode",
                "key": self.places_api_key
            }

            response = requests.get(url, params=params)

            if response.status_code != 200:
                st.error(f"API Error: Status Code {response.status_code}")
                return []

            data = response.json()

            if data['status'] != 'OK':
                st.error(f"API Error: {data['status']}")
                if 'error_message' in data:
                    st.error(f"Error Message: {data['error_message']}")
                return []

            return [prediction['description'] for prediction in data.get('predictions', [])]

        except requests.RequestException as e:
            st.error(f"Location suggestion error: {str(e)}")
            return []

    def get_location_coordinates(self, location: str) -> Optional[Dict[str, Any]]:
        """Convert location string to coordinates using Geocoding API."""
        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                "address": location,
                "key": self.places_api_key
            }

            response = requests.get(url, params=params)

            if response.status_code != 200:
                st.error(f"Geocoding API Error: Status Code {response.status_code}")
                return None

            data = response.json()

            if data['status'] != 'OK':
                st.error(f"Geocoding Error: {data['status']}")
                if 'error_message' in data:
                    st.error(f"Error Message: {data['error_message']}")
                return None

            location_data = data['results'][0]
            coords = location_data['geometry']['location']
            return {
                'lat': coords['lat'],
                'lng': coords['lng'],
                'formatted_address': location_data['formatted_address']
            }

        except requests.RequestException as e:
            st.error(f"Geocoding API Error: {str(e)}")
            return None

    def get_nearby_restaurants(self, location_data: Dict[str, Any],
                               establishment_type: str, radius: int) -> List[Dict[str, Any]]:
        """Find nearby restaurants using Google Places API with pagination."""
        try:
            all_results = []
            url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                "location": f"{location_data['lat']},{location_data['lng']}",
                "radius": radius,
                "type": establishment_type.lower(),
                "key": self.places_api_key,
                "opennow": True
            }

            # Fetch first page
            with st.spinner("Fetching restaurants (page 1)..."):
                response = requests.get(url, params=params)
                data = response.json()
                page_count = 1

                while True:
                    if data['status'] != 'OK' and data['status'] != 'ZERO_RESULTS':
                        st.error(f"Places API Error: {data['status']}")
                        if 'error_message' in data:
                            st.error(f"Error Message: {data['error_message']}")
                        break

                    # Process current page results
                    current_page_results = []
                    for place in data.get('results', []):
                        details = self.get_place_details(place['place_id'])
                        if details:
                            current_page_results.append(details)

                    all_results.extend(current_page_results)
                    st.success(f"Found {len(current_page_results)} places on page {page_count}")

                    # Check if we should continue pagination
                    if len(all_results) >= st.session_state.max_results or 'next_page_token' not in data:
                        break

                    # Wait before next request (required by Google)
                    time.sleep(2)
                    page_count += 1

                    # Fetch next page
                    with st.spinner(f"Fetching restaurants (page {page_count})..."):
                        params['pagetoken'] = data['next_page_token']
                        response = requests.get(url, params=params)
                        data = response.json()

            if not all_results:
                st.warning("No establishments found in this area. Try increasing the distance.")

            return all_results

        except requests.RequestException as e:
            st.error(f"Restaurant Search Error: {str(e)}")
            return []

    def get_place_details(self, place_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific place."""
        try:
            url = "https://maps.googleapis.com/maps/api/place/details/json"
            params = {
                "place_id": place_id,
                "fields": ("name,rating,reviews,price_level,photos,formatted_address,"
                           "opening_hours,types,website,user_ratings_total"),
                "key": self.places_api_key,
                "reviews_sort": "most_relevant"
            }

            response = requests.get(url, params=params)
            if response.status_code != 200:
                st.error(f"Place Details API Error: Status Code {response.status_code}")
                return None

            return response.json().get('result')

        except requests.RequestException as e:
            st.error(f"Place Details Error: {str(e)}")
            return None

    def get_place_photo(self, photo_reference: str, max_width: int = 400) -> Optional[str]:
        """Get photo URL for a place."""
        if not photo_reference:
            return None

        return (f"https://maps.googleapis.com/maps/api/place/photo"
                f"?maxwidth={max_width}&photoreference={photo_reference}"
                f"&key={self.places_api_key}")


class AIRecommender:
    """Handles AI-powered restaurant recommendations using Google's Gemini API."""

    def __init__(self):
        """Initialize the AI recommender with Gemini configuration."""
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.generation_config = {
            "temperature": 0.7,
            "max_output_tokens": 1000,
            "top_p": 0.9
        }

    def generate_questions(self, restaurants_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate questions based on restaurant characteristics and review content."""
        restaurants_summary = self._create_restaurants_summary(restaurants_data)

        prompt = f"""
        You are a friendly AI helping users choose from {len(restaurants_data)} available restaurants. You will ask questions to users.
        I'm providing you with detailed restaurant data including reviews: {restaurants_summary}

        Based on the actual reviews and restaurant characteristics, create 5 multiple-choice questions that will help you shortlist one restaurant. The questions should be generic and NOT mention any restaurant name.

        Important Guidelines:

        1.  Base questions on the available information, including reviews. Focus on:
            *   Common themes in reviews (e.g., "great for groups," "excellent service")
            *   Specific experiences described by customers (e.g., "amazing cocktails," "long wait times")
            *   Notable features or dishes mentioned repeatedly (e.g., "rooftop terrace," "signature pasta dish")
            *   Atmosphere and ambiance described in reviews (e.g., "cozy and intimate," "loud and lively")
            *   Service quality observations (e.g., "attentive staff," "slow service")

        2.  Each question should:
            *   Be a general question about dining preferences (e.g., "What's the occasion?", "What kind of atmosphere are you looking for?")
            *   Have 4 options that are derived from the *actual data* (reviews, descriptions, features) of the available restaurants. The options should reflect real features or experiences described.
            *   Help differentiate between the available restaurants.

        3.  Question Categories (General Question Examples):
            *   **Occasion/Purpose:** (e.g., "What's the occasion?", "Who are you dining with?")
            *   **Ambiance/Atmosphere:** (e.g., "What kind of atmosphere are you looking for?", "What's your preferred noise level?")
            *   **Food/Cuisine Preferences:** (e.g., "What type of cuisine are you in the mood for?", "Are there any dietary restrictions?")
            *   **Price Range:** (e.g., "What's your budget for this meal?", "How much are you willing to spend per person?")
            *   **Service Style:** (e.g., "What kind of service are you expecting?", "How important is the speed of service?")
            *   **Additional Considerations:** (e.g., "Are you looking for any specific amenities?", "How important is the location?")

        Format EXACTLY like this:

        Question 1: [General Question Text]
        A) [Option 1 - derived from restaurant data]
        B) [Option 2 - derived from restaurant data]
        C) [Option 3 - derived from restaurant data]
        D) [Option 4 - derived from restaurant data]

        **Example:**

        Question 1: What kind of atmosphere are you hoping for?
        A) Relaxed and family-friendly 
        B) Lively and energetic with a bar scene 
        C) Intimate and romantic with soft lighting 
        D) Modern and minimalist with a focus on design 

        """

        try:
            response = self.model.generate_content(prompt)
            return self._parse_questions(response.text)
        except Exception as e:
            st.error(f"Question generation error: {str(e)}")
            return None

    def _create_restaurants_summary(self, restaurants: List[Dict[str, Any]]) -> str:
        """Create a detailed summary of restaurants including reviews and all available data."""
        detailed_summaries = []

        for idx, restaurant in enumerate(restaurants):
            # Create a comprehensive summary for each restaurant
            restaurant_summary = {
                'index': idx,
                'name': restaurant.get('name', 'Unknown'),
                'rating': restaurant.get('rating', 'N/A'),
                'total_ratings': restaurant.get('user_ratings_total', 0),
                'price_level': restaurant.get('price_level', 'N/A'),
                'types': restaurant.get('types', []),
                'reviews': []
            }

            # Add detailed review information
            if 'reviews' in restaurant:
                for review in restaurant['reviews'][:5]:  # Get top 5 reviews
                    review_summary = {
                        'rating': review.get('rating', 'N/A'),
                        'text': review.get('text', ''),
                        'time': review.get('relative_time_description', '')
                    }
                    restaurant_summary['reviews'].append(review_summary)

            detailed_summaries.append(restaurant_summary)

        return json.dumps(detailed_summaries, ensure_ascii=False)

    def _parse_questions(self, questions_text: str) -> List[Dict[str, Any]]:
        """Parse the generated questions into a structured format."""
        lines = questions_text.strip().split('\n')
        questions = []
        current_question = None
        current_options = []

        for line in lines:
            line = line.strip()
            if line.startswith('Question'):
                if current_question:
                    questions.append({
                        'question': current_question,
                        'options': current_options
                    })
                current_question = line.split(':', 1)[1].strip()
                current_options = []
            elif line.startswith(('A)', 'B)', 'C)', 'D)')):
                option = line[3:].strip()
                current_options.append(option)

        if current_question:
            questions.append({
                'question': current_question,
                'options': current_options
            })

        return questions

    def get_recommendation(self, restaurants_data: List[Dict[str, Any]],
                           user_answers: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Generate a detailed restaurant recommendation based on user answers and review analysis.
        The function analyzes review content, matching patterns with user preferences.
        """
        # First, create a comprehensive data structure with restaurant details and reviews
        detailed_analysis = self._create_detailed_restaurant_analysis(restaurants_data)

        # Create a context-rich prompt that includes all relevant information
        prompt = f"""
        You are a sophisticated restaurant recommendation system analyzing detailed restaurant data 
        and user preferences to find the perfect match.

        RESTAURANT DATA:
        {json.dumps(detailed_analysis, ensure_ascii=False)}

        USER PREFERENCES:
        {json.dumps(user_answers, ensure_ascii=False)}

        TASK:
        1. Analyze each restaurant's reviews and characteristics
        2. Compare them with user preferences
        3. Generate a detailed matching score and reasoning
        4. Select the best match

        You must return ONLY a JSON object with these exact fields:
        {{
            "selected_restaurant_index": (number between 0 and {len(restaurants_data) - 1}),
            "reasoning": {{
                "main_reason": "Primary reason for selection",
                "review_evidence": [
                    "Up to 3 specific review quotes that support this choice"
                ],
                "preference_matching": {{
                    "strength_points": [
                        "List of ways this restaurant matches user preferences"
                    ],
                    "consideration_points": [
                        "Any points user should be aware of"
                    ]
                }}
            }}
        }}
        """

        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()

            # Parse and validate the response
            try:
                recommendation = json.loads(response_text)

                # Validate recommendation structure
                self._validate_recommendation_structure(recommendation, len(restaurants_data))

                # Format the reasoning for display
                formatted_reasoning = self._format_reasoning_for_display(recommendation['reasoning'])

                return {
                    "selected_restaurant_index": recommendation["selected_restaurant_index"],
                    "reasoning": formatted_reasoning
                }

            except json.JSONDecodeError:
                return self._generate_fallback_recommendation(restaurants_data)

        except Exception as e:
            st.error(f"Recommendation error: {str(e)}")
            return self._generate_fallback_recommendation(restaurants_data)

    def _create_detailed_restaurant_analysis(self, restaurants_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Create a detailed analysis of each restaurant including review content analysis.
        This helps in making more informed recommendations.
        """
        analyzed_restaurants = []

        for idx, restaurant in enumerate(restaurants_data):
            # Basic restaurant information
            restaurant_analysis = {
                "index": idx,
                "name": restaurant.get("name", "Unknown"),
                "rating": restaurant.get("rating", 0),
                "price_level": restaurant.get("price_level", 0),
                "total_reviews": restaurant.get("user_ratings_total", 0),

                # Detailed review analysis
                "review_analysis": {
                    "common_themes": [],
                    "mentioned_dishes": [],
                    "atmosphere_descriptions": [],
                    "service_comments": [],
                    "positive_highlights": [],
                    "consideration_points": []
                }
            }

            # Analyze reviews if available
            if "reviews" in restaurant:
                review_texts = [review.get("text", "") for review in restaurant["reviews"][:5]]
                restaurant_analysis["review_content"] = review_texts

                # Add full review details for context
                restaurant_analysis["detailed_reviews"] = [
                    {
                        "rating": review.get("rating", 0),
                        "text": review.get("text", ""),
                        "time": review.get("relative_time_description", ""),
                        "author": review.get("author_name", "Anonymous")
                    }
                    for review in restaurant["reviews"][:5]
                ]

            analyzed_restaurants.append(restaurant_analysis)

        return analyzed_restaurants

    def _validate_recommendation_structure(self, recommendation: Dict[str, Any], max_index: int) -> None:
        """
        Validate the structure and content of the AI's recommendation.
        Raises ValueError if the recommendation format is invalid.
        """
        required_fields = {
            "selected_restaurant_index": lambda x: isinstance(x, (int, float)) and 0 <= int(x) < max_index,
            "reasoning": lambda x: isinstance(x, dict) and all(
                field in x for field in ["main_reason", "review_evidence", "preference_matching"]
            )
        }

        for field, validator in required_fields.items():
            if field not in recommendation or not validator(recommendation[field]):
                raise ValueError(f"Invalid or missing field: {field}")

    def _format_reasoning_for_display(self, reasoning: Dict[str, Any]) -> str:
        """
        Format the AI's reasoning into a user-friendly display string.
        Creates a well-structured explanation of the recommendation.
        """
        formatted_text = f"🎯 {reasoning['main_reason']}\n\n"

        # Add review evidence
        formatted_text += "📝 Supporting Reviews:\n"
        for quote in reasoning['review_evidence']:
            formatted_text += f"• "
            {quote}
            "\n"
        formatted_text += "\n"

        # Add strength points
        formatted_text += "✨ Perfect Match Points:\n"
        for point in reasoning['preference_matching']['strength_points']:
            formatted_text += f"• {point}\n"
        formatted_text += "\n"

        # Add consideration points if any
        if reasoning['preference_matching']['consideration_points']:
            formatted_text += "💡 Good to Know:\n"
            for point in reasoning['preference_matching']['consideration_points']:
                formatted_text += f"• {point}\n"

        return formatted_text

    def _generate_fallback_recommendation(self, restaurants_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate a basic fallback recommendation if the AI analysis fails.
        Selects the highest-rated restaurant as a safe choice.
        """
        # Find the highest-rated restaurant as a fallback
        highest_rated = max(
            enumerate(restaurants_data),
            key=lambda x: (x[1].get('rating', 0), x[1].get('user_ratings_total', 0))
        )

        return {
            "selected_restaurant_index": highest_rated[0],
            "reasoning": (
                "Based on overall ratings and number of reviews, "
                "this restaurant stands out as a reliable choice. "
                f"It has a rating of {highest_rated[1].get('rating', 'N/A')} "
                f"from {highest_rated[1].get('user_ratings_total', 0)} reviews."
            )
        }


def display_final_recommendation(restaurant: Dict[str, Any], reasoning: str):
    """Display the final restaurant recommendation with detailed explanation."""
    st.title("🎉 Your Perfect Restaurant Match!")

    with st.container():
        # Display restaurant name and basic info
        st.header(restaurant.get('name', 'Unknown'))

        # Display photos if available
        if restaurant.get('photos'):
            photo_urls = [
                RestaurantFinder().get_place_photo(photo['photo_reference'])
                for photo in restaurant['photos'][:3]
            ]
            cols = st.columns(len(photo_urls))
            for idx, url in enumerate(photo_urls):
                if url:
                    cols[idx].image(url)

        # Basic information
        st.subheader("📍 Location")
        st.write(restaurant.get('formatted_address', 'Address not available'))

        st.subheader("⭐ Rating")
        st.write(f"{restaurant.get('rating', 'N/A')} ({restaurant.get('user_ratings_total', 0)} reviews)")

        if 'price_level' in restaurant:
            st.subheader("💰 Price Level")
            st.write('$' * restaurant['price_level'])

        # AI's reasoning
        st.subheader("🤖 Why This Restaurant?")
        st.write(reasoning)

        # Additional details
        if restaurant.get('website'):
            st.markdown(f"🌐 [Visit Website]({restaurant['website']})")

        # Display reviews
        if restaurant.get('reviews'):
            st.subheader("📝 Recent Reviews")
            for review in restaurant['reviews'][:3]:
                with st.expander(f"⭐ {review.get('rating', 'N/A')} - {review.get('author_name', 'Anonymous')}"):
                    st.write(review.get('text', 'No comment'))
                    st.write(f"Posted: {review.get('relative_time_description', '')}")


def main():
    """Main application flow."""
    initialize_session_state()

    # Initialize classes
    try:
        finder = RestaurantFinder()
        ai_recommender = AIRecommender()
    except Exception as e:
        st.error(f"Initialization error: {str(e)}")
        return

    # Display progress bar
    st.progress(st.session_state.step / st.session_state.total_steps)

    # Step 1: Location Selection
    if st.session_state.step == 1:
        st.title("🍽️ AI Restaurant Finder")
        st.write("Let's find your perfect dining spot!")

        location_input = st.text_input("Enter a city or location:", key="location_search")

        if location_input:
            with st.spinner("Searching locations..."):
                suggestions = finder.get_place_suggestions(location_input)

                if suggestions:
                    selected_location = st.selectbox(
                        "Select your location:",
                        suggestions,
                        key="location_select"
                    )

                    if st.button("Next", key="location_next"):
                        with st.spinner("Getting location details..."):
                            location_data = finder.get_location_coordinates(selected_location)
                            if location_data:
                                st.session_state.location = selected_location
                                st.session_state.location_data = location_data
                                st.session_state.step = 2
                                st.rerun()
                else:
                    st.warning(f"No locations found for '{location_input}'. Please try a different location.")

    # Step 2: Distance Selection
    elif st.session_state.step == 2:
        st.title("How far would you like to search?")

        distance_options = {
            "Within 1 km": 1000,
            "Within 3 km": 3000,
            "Within 5 km": 5000,
            "Within 10 km": 10000,
            "Within 20 km": 20000
        }

        selected_distance = st.radio("Select distance", list(distance_options.keys()))

        if st.button("Next"):
            st.session_state.distance = distance_options[selected_distance]
            st.session_state.step = 3
            st.rerun()

    # Step 3: Establishment Type Selection
    elif st.session_state.step == 3:
        st.title("What type of place are you looking for?")

        establishment_types = [
            "Restaurant",
            "Cafe",
            "Bar",
            "Pub",
            "Food truck",
            "Bakery",
            "Ice cream shop",
            "Fast food restaurant"
        ]

        selected_type = st.radio("Select establishment type", establishment_types)

        if st.button("Search"):
            st.session_state.establishment_type = selected_type
            # Fetch restaurants
            with st.spinner("Finding places..."):
                restaurants = finder.get_nearby_restaurants(
                    st.session_state.location_data,
                    st.session_state.establishment_type,
                    st.session_state.distance
                )

                if restaurants:
                    st.session_state.restaurants_data = restaurants
                    st.session_state.step = 4
                    st.rerun()
                else:
                    st.error("No establishments found. Try different criteria.")

    # Step 4: AI Questions
    elif st.session_state.step == 4:
        st.title("Help Us Find Your Perfect Match!")

        if not st.session_state.questions:
            with st.spinner("Analyzing available restaurants..."):
                questions = ai_recommender.generate_questions(st.session_state.restaurants_data)
                st.session_state.questions = questions

        if st.session_state.questions:
            current_q = st.session_state.questions[st.session_state.current_question]

            st.subheader(f"Question {st.session_state.current_question + 1} of 5")
            st.write(current_q['question'])

            answer = st.radio("Select your preference:", current_q['options'])

            if st.button("Next" if st.session_state.current_question < 4 else "Get Recommendation"):
                st.session_state.answers[f"Q{st.session_state.current_question + 1}"] = answer

                if st.session_state.current_question < 4:
                    st.session_state.current_question += 1
                    st.rerun()
                else:
                    st.session_state.step = 5
                    st.rerun()
        else:
            st.error("Failed to generate questions. Please try again.")
            if st.button("Restart"):
                initialize_session_state()
                st.rerun()

    # Step 5: Final Recommendation
    elif st.session_state.step == 5:
        with st.spinner("Finding your perfect match..."):
            recommendation = ai_recommender.get_recommendation(
                st.session_state.restaurants_data,
                st.session_state.answers
            )

            if recommendation and 'selected_restaurant_index' in recommendation:
                selected_restaurant = st.session_state.restaurants_data[
                    recommendation['selected_restaurant_index']
                ]
                display_final_recommendation(selected_restaurant, recommendation['reasoning'])
            else:
                st.error("Failed to generate recommendation. Please try again.")

        if st.button("Start New Search"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            initialize_session_state()
            st.rerun()


if __name__ == "__main__":
    main()