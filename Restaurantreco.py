# AI restaurant model
import streamlit as st
import requests
import google.generativeai as genai
import os
from dotenv import load_dotenv
import json
import re
import urllib.parse
from typing import List, Dict, Any, Optional

load_dotenv()

st.set_page_config(
    page_title="AI Restaurant Finder",
    page_icon="🍽️",
    layout="centered"
)

# GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GOOGLE_PLACES_API_KEY = st.secrets["GOOGLE_PLACES_API_KEY"]
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

def initialize_session_state():
    default_state = {
        'step': 1,
        'total_steps': 6,
        'location': None,
        'location_data': None,
        'establishment_type': None,
        'distance': None,
        'restaurants_data': None,
        'max_results': 20,
        'current_question': 0,
        'questions': None,
        'answers': {},
        'final_recommendation': None
    }

    for key, value in default_state.items():
        if key not in st.session_state:
            st.session_state[key] = value


class RestaurantFinder:
    def __init__(self):
        self.places_api_key = GOOGLE_PLACES_API_KEY

    def get_place_suggestions(self, input_text: str) -> List[str]:
        url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
        params = {
            "input": input_text,
            "types": "geocode",
            "key": self.places_api_key
        }
        response = requests.get(url, params=params)
        data = response.json()
        return [prediction['description'] for prediction in data.get('predictions', [])]

    def get_location_coordinates(self, location: str) -> Optional[Dict[str, Any]]:
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": location,
            "key": self.places_api_key
        }
        response = requests.get(url, params=params)
        data = response.json()
        if data['status'] == 'OK':
            location_data = data['results'][0]
            coords = location_data['geometry']['location']
            return {
                'lat': coords['lat'],
                'lng': coords['lng'],
                'formatted_address': location_data['formatted_address']
            }
        return None

    def get_nearby_restaurants(self, location_data: Dict[str, Any],
                               establishment_type: str, radius: int) -> List[Dict[str, Any]]:
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            "location": f"{location_data['lat']},{location_data['lng']}",
            "radius": radius,
            "type": establishment_type.lower(),
            "key": self.places_api_key,
            "opennow": True
        }

        response = requests.get(url, params=params)
        data = response.json()
        results = []

        if data['status'] == 'OK':
            for place in data.get('results', [])[:20]:
                details = self.get_place_details(place['place_id'])
                if details:
                    results.append(details)

        return results

    def get_place_details(self, place_id: str) -> Optional[Dict[str, Any]]:
        url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            "place_id": place_id,
            "fields": ("name,rating,reviews,price_level,photos,formatted_address,"
                       "opening_hours,types,website,user_ratings_total"),
            "key": self.places_api_key,
            "reviews_sort": "most_relevant"
        }
        response = requests.get(url, params=params)
        return response.json().get('result')

    def get_place_photo(self, photo_reference: str, max_width: int = 400) -> Optional[str]:
        if not photo_reference:
            return None
        return (f"https://maps.googleapis.com/maps/api/place/photo"
                f"?maxwidth={max_width}&photoreference={photo_reference}"
                f"&key={self.places_api_key}")


class AIRecommender:
    def __init__(self):
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.generation_config = {
            "temperature": 0.7,
            "max_output_tokens": 1000,
            "top_p": 0.9
        }

    def generate_questions(self, restaurants_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        restaurants_summary = self._create_restaurants_summary(restaurants_data)
        prompt = f"""
        You are an AI restaurant recommendation system analyzing {len(restaurants_data)} restaurants.
        Based on the restaurant data provided, generate EXACTLY 5 multiple-choice questions.

        Format MUST be EXACTLY as follows, including question numbers and option letters:

        Question 1: [Question text]
        A) [Option text]
        B) [Option text]
        C) [Option text]
        D) [Option text]

        Question 2: [Question text]
        A) [Option text]
        B) [Option text]
        C) [Option text]
        D) [Option text]

        [Continue for all 5 questions]

        IMPORTANT RULES:
        1. EXACTLY 5 questions
        2. EXACTLY 4 options (A through D) per question
        3. Use EXACTLY this format with question numbers and option letters
        4. Questions should be about dining preferences (atmosphere, price, cuisine type, etc.)
        5. Base options on actual characteristics found in the restaurant data
        6. Do not mention specific restaurant names in questions or options

        Restaurant data for reference:
        {restaurants_summary}
        """

        response = self.model.generate_content(prompt)
        return self._parse_questions(response.text)

    def _create_restaurants_summary(self, restaurants: List[Dict[str, Any]]) -> str:
        detailed_summaries = []
        for idx, restaurant in enumerate(restaurants):
            summary = {
                'index': idx,
                'name': restaurant.get('name', 'Unknown'),
                'rating': restaurant.get('rating', 'N/A'),
                'total_ratings': restaurant.get('user_ratings_total', 0),
                'price_level': restaurant.get('price_level', 'N/A'),
                'types': restaurant.get('types', []),
                'reviews': []
            }

            if 'reviews' in restaurant:
                for review in restaurant['reviews'][:5]:
                    review_summary = {
                        'rating': review.get('rating', 'N/A'),
                        'text': review.get('text', ''),
                        'time': review.get('relative_time_description', '')
                    }
                    summary['reviews'].append(review_summary)

            detailed_summaries.append(summary)

        return json.dumps(detailed_summaries, ensure_ascii=False)

    def _parse_questions(self, text: str) -> List[Dict[str, Any]]:
        questions = []
        current_question = None
        current_options = []

        lines = text.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith('Question'):
                if current_question and len(current_options) == 4:
                    questions.append({
                        'question': current_question,
                        'options': current_options.copy()
                    })

                current_question = line.split(':', 1)[1].strip()
                current_options = []

            elif line.startswith(('A)', 'B)', 'C)', 'D)')):
                option = line[3:].strip()
                current_options.append(option)

        if current_question and len(current_options) == 4:
            questions.append({
                'question': current_question,
                'options': current_options
            })

        return questions

    def get_recommendation(self, restaurants_data: List[Dict[str, Any]],
                           user_answers: Dict[str, str]) -> Optional[Dict[str, Any]]:
        detailed_analysis = self._create_detailed_restaurant_analysis(restaurants_data)

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
                "main_reason": "Primary reason for selection. The reason should be like you are talking to a friend",
                "review_evidence": [
                    "Up to 3 specific review quotes that support this choice"
                ],
                "preference_matching": {{
                    "strength_points": [
                        "List of ways this restaurant matches user preferences. Do not mention the question number in strength points"
                    ],
                    "consideration_points": [
                        "Any points user should be aware of"
                    ]
                }}
            }}
        }}

        Return ONLY the JSON object, without any markdown formatting or additional text.
        """

        response = self.model.generate_content(prompt)
        cleaned_response = self._clean_ai_response(response.text)
        return json.loads(cleaned_response)

    def _create_detailed_restaurant_analysis(self, restaurants: List[Dict[str, Any]]) -> Dict[str, Any]:
        detailed_analysis = []

        for idx, restaurant in enumerate(restaurants):
            analysis = {
                'index': idx,
                'name': restaurant.get('name', 'Unknown'),
                'basic_info': {
                    'rating': restaurant.get('rating', 0),
                    'total_ratings': restaurant.get('user_ratings_total', 0),
                    'price_level': restaurant.get('price_level', 0),
                    'types': restaurant.get('types', []),
                },
                'atmosphere_indicators': {
                    'is_upscale': any(keyword in str(restaurant).lower()
                                      for keyword in ['fine dining', 'upscale', 'luxury']),
                    'is_casual': any(keyword in str(restaurant).lower()
                                     for keyword in ['casual', 'relaxed', 'family']),
                    'is_lively': any(keyword in str(restaurant).lower()
                                     for keyword in ['bustling', 'lively', 'energetic']),
                    'is_cozy': any(keyword in str(restaurant).lower()
                                   for keyword in ['cozy', 'intimate', 'quiet'])
                },
                'cuisine_analysis': {
                    'cuisine_types': [t for t in restaurant.get('types', [])
                                      if 'food' in t or 'restaurant' in t],
                    'has_buffet': any('buffet' in str(review.get('text', '')).lower()
                                      for review in restaurant.get('reviews', []))
                },
                'review_summary': []
            }

            if 'reviews' in restaurant:
                for review in restaurant['reviews']:
                    review_text = review.get('text', '').lower()
                    review_analysis = {
                        'rating': review.get('rating', 0),
                        'text': review.get('text', ''),
                        'mentions': {
                            'food_quality': any(word in review_text
                                                for word in ['delicious', 'tasty', 'food']),
                            'service': any(word in review_text
                                           for word in ['service', 'staff', 'waiter']),
                            'ambiance': any(word in review_text
                                            for word in ['ambiance', 'atmosphere', 'decor']),
                            'value': any(word in review_text
                                         for word in ['price', 'value', 'worth'])
                        }
                    }
                    analysis['review_summary'].append(review_analysis)

            detailed_analysis.append(analysis)

        return {
            'restaurants': detailed_analysis,
            'total_analyzed': len(detailed_analysis),
            'analysis_version': '1.0'
        }

    def _clean_ai_response(self, response_text: str) -> str:
        response_text = re.sub(r'^```json\s*', '', response_text, flags=re.MULTILINE)
        response_text = re.sub(r'^```\s*$', '', response_text, flags=re.MULTILINE)
        return response_text.strip()

def display_final_recommendation(restaurant: Dict[str, Any], recommendation_data: Dict[str, Any]):
    st.title(f"🎉 I've Found Your Perfect Spot: {restaurant.get('name', 'Unknown')}!")

    # Photo Gallery
    if restaurant.get('photos'):
        photo_urls = [
            RestaurantFinder().get_place_photo(photo['photo_reference'])
            for photo in restaurant['photos'][:3]
        ]
        cols = st.columns(len(photo_urls))
        for idx, url in enumerate(photo_urls):
            if url:
                cols[idx].image(url)

    # Enthusiastic Introduction
    st.markdown("### 🌟 Why You're Going to Love This Place")
    main_reason = recommendation_data.get('main_reason', '')
    strength_points = recommendation_data.get('preference_matching', {}).get('strength_points', [])

    enthusiasm_intro = f"""
    {main_reason}

    What makes it special? """

    highlights = " ".join(f"✨ {point.lower()}. " for point in strength_points)
    st.write(enthusiasm_intro + highlights)

    # Quick Facts in a Friendly Format
    st.markdown("### 🎯 Quick Take")
    quick_facts_col1, quick_facts_col2 = st.columns(2)

    with quick_facts_col1:
        if restaurant.get('rating'):
            st.write(
                f"💫 Rated {restaurant.get('rating', 'N/A')}/5.0 by {restaurant.get('user_ratings_total', 0)} happy diners")

    with quick_facts_col2:
        address = restaurant.get('formatted_address', 'Address not available')
        maps_url = f"https://www.google.com/maps/dir/?api=1&destination={urllib.parse.quote(address)}"
        st.write(f"📍 Located at: {address}")

    # Featured Reviews as Conversations
    if restaurant.get('reviews'):
        st.markdown("### 💬 Here's What Others Are Saying")
        top_reviews = sorted(
            restaurant['reviews'],
            key=lambda x: (x.get('rating', 0), len(x.get('text', ''))),
            reverse=True
        )[:3]

        for review in top_reviews:
            with st.expander("💫 Read this amazing review"):
                st.write(f"\"{review.get('text', 'No comment')}\"")
                st.write(f"- Shared {review.get('relative_time_description', '')}")

    # Call to Action
    st.markdown("### 🎊 Ready to Try It?")
    action_col1, action_col2 = st.columns(2)

    with action_col1:
        st.markdown(f"[🚗 Get Directions]({maps_url})")

    with action_col2:
        if restaurant.get('website'):
            st.markdown(f"[🌐 Check Out Their Menu]({restaurant['website']})")


def main():
    initialize_session_state()
    finder = RestaurantFinder()
    ai_recommender = AIRecommender()
    st.progress(st.session_state.step / st.session_state.total_steps)

    if st.session_state.step == 1:
        st.title("🍽️ AI Restaurant Finder")
        st.write("Let's find your perfect dining spot!")
        location_input = st.text_input("Enter a city or location:", key="location_search")

        if location_input:
            suggestions = finder.get_place_suggestions(location_input)

            if suggestions:
                selected_location = st.selectbox(
                    "Select your location:",
                    suggestions,
                    key="location_select"
                )

                if st.button("Next", key="location_next"):
                    location_data = finder.get_location_coordinates(selected_location)
                    if location_data:
                        st.session_state.location = selected_location
                        st.session_state.location_data = location_data
                        st.session_state.step = 2
                        st.rerun()

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

        if st.button("Start New Search"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            initialize_session_state()
            st.rerun()


if __name__ == "__main__":
    main()