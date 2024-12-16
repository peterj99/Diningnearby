import streamlit as st
import google.generativeai as genai
import requests
#import os
import json
import re
# from dotenv import load_dotenv
#
# # Load environment variables
# load_dotenv()

# Configuration
GOOGLE_PLACES_API_KEY = st.secrets["GOOGLE_PLACES_API_KEY"]
GEMINI_API_KEY = st.secrest["GEMINI_API_KEY"]


class RestaurantRecommender:
    def __init__(self):
        # Configure Gemini
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-1.5-flash')

        # Generation config
        self.generation_config = {
            "temperature": 0.7,
            "max_output_tokens": 1000,
            "top_p": 0.9
        }

    def get_place_suggestions(self, input_text):
        """Fetch place suggestions using Google Places Autocomplete"""
        url = f"https://maps.googleapis.com/maps/api/place/autocomplete/json?input={input_text}&types=geocode&key={GOOGLE_PLACES_API_KEY}"
        try:
            response = requests.get(url)
            suggestions = response.json().get('predictions', [])
            return [prediction['description'] for prediction in suggestions]
        except Exception as e:
            st.error(f"Location suggestion error: {e}")
            return []

    def get_location_coordinates(self, location):
        """Get latitude and longitude for a location"""
        geocoding_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={location}&key={GOOGLE_PLACES_API_KEY}"

        try:
            geo_response = requests.get(geocoding_url)
            location_data = geo_response.json()

            if location_data['status'] != 'OK':
                st.error("Location coordinates not found.")
                return None

            coords = location_data['results'][0]['geometry']['location']
            return f"{coords['lat']},{coords['lng']}"
        except Exception as e:
            st.error(f"Geocoding error: {e}")
            return None

    def generate_comprehensive_questions(self):
        """Generate a comprehensive set of restaurant preference questions"""
        prompt = """
        You are a friendly AI chatbot helping someone find the perfect dining experience. 
        Create 7 multiple-choice questions that will help narrow down restaurant preferences. 
        Question Flow: The bot should ask a series of questions to gather user preferences. Start with broader categories (e.g. cuisine) and then narrow down the choices based on the user's responses.
        Each question should:
        - Be conversational and friendly
        - Have 4 clear, distinct options
        - Cover different aspects of dining preferences
        
        AVOID giving fictional establishments. If you do not have matching establishments, you can give establishments which do not satisfy all the conditions. You need to rank the output based on how much it will satisfy the users needs.

        Format EXACTLY like this:
        Question X: [Friendly question text]
        A) [Option 1]
        B) [Option 2]
        C) [Option 3]
        D) [Option 4]

        Questions about:
        1. Dining atmosphere
        2. Cuisine type
        3. Price range
        4. Dining style
        5. Occasion type
        6. Dietary preferences
        7. Dining group composition
        """

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config
            )
            return response.text.strip()
        except Exception as e:
            st.error(f"Question generation error: {e}")
            return ""

    def recommend_restaurants(self, location_coords, user_preferences):
        """Generate restaurant recommendations"""
        prompt = f"""
        You are a helpful AI recommending restaurants. 
        Location Coordinates: {location_coords}
        User Preferences: {json.dumps(user_preferences)}

        Generate 5 restaurant recommendations that match the user's preferences:

        For EACH recommendation, provide:
        - Establishment Name
        - Brief Description
        - Type of Establishment
        - Specific Rationale linking to user preferences

        Ensure recommendations are:
        - Diverse
        - Aligned with user preferences
        - Realistic and appealing
        """

        try:
            response = self.model.generate_content(
                prompt,
                generation_config=self.generation_config
            )
            return response.text
        except Exception as e:
            st.error(f"Recommendation generation error: {e}")
            return "Unable to generate recommendations"


def parse_questions_and_options(questions_text):
    """
    Parse questions and options from the generated text
    Returns a list of dictionaries with 'question' and 'options'
    """
    # Split the text into lines and clean them
    lines = [line.strip() for line in questions_text.split('\n') if line.strip()]

    parsed_questions = []
    current_question = None
    current_options = []

    for line in lines:
        # Check if line is a question
        question_match = re.match(r'Question (\d+):\s*(.+)', line)
        if question_match:
            # If we had a previous question, add it to the list
            if current_question:
                parsed_questions.append({
                    'question': current_question,
                    'options': current_options
                })

            # Start a new question
            current_question = question_match.group(2)
            current_options = []
            continue

        # Check if line is an option
        option_match = re.match(r'([A-D])\)\s*(.+)', line)
        if option_match and current_question:
            current_options.append(option_match.group(2))

    # Add the last question
    if current_question:
        parsed_questions.append({
            'question': current_question,
            'options': current_options
        })

    return parsed_questions


def initialize_session_state():
    """Initialize session state variables if they don't exist"""
    default_state = {
        'stage': 'location',
        'location': None,
        'location_coords': None,
        'questions': None,
        'parsed_questions': None,
        'current_question': 0,
        'answers': {}
    }

    for key, value in default_state.items():
        if key not in st.session_state:
            st.session_state[key] = value


def main():
    st.set_page_config(page_title="AI Restaurant Finder", page_icon="🍽️", layout="centered")
    st.title("🍽️ AI Restaurant Recommender")

    # Initialize recommender and session state
    recommender = RestaurantRecommender()
    initialize_session_state()

    # Location Selection Stage
    if st.session_state.stage == 'location':
        st.header("Where are you dining today?")
        location_input = st.text_input("Enter your location", key="location_search")

        if location_input:
            suggestions = recommender.get_place_suggestions(location_input)
            if suggestions:
                selected_location = st.selectbox("Select your location", suggestions)

                if st.button("Confirm Location"):
                    st.session_state.location = selected_location
                    st.session_state.location_coords = recommender.get_location_coordinates(selected_location)

                    if st.session_state.location_coords:
                        # Generate questions
                        st.session_state.questions = recommender.generate_comprehensive_questions()

                        # Parse questions
                        st.session_state.parsed_questions = parse_questions_and_options(st.session_state.questions)

                        st.session_state.stage = 'questions'
                        st.session_state.current_question = 0
                        st.rerun()
                    else:
                        st.warning("Could not find coordinates for this location.")

    # Questions Stage
    elif st.session_state.stage == 'questions':
        # Ensure parsed questions exist
        if not st.session_state.parsed_questions:
            st.warning("Questions could not be generated. Please try again.")
            if st.button("Restart"):
                initialize_session_state()
                st.rerun()
            st.stop()

        # Get current question
        questions = st.session_state.parsed_questions
        current_question_data = questions[st.session_state.current_question]

        # Display current question
        st.header(f"Question {st.session_state.current_question + 1}")
        st.write(current_question_data['question'])

        # Display options
        current_options = current_question_data['options']

        if current_options:
            answer = st.radio("Choose your preference", current_options)

            if st.button("Next Question"):
                # Store answer
                st.session_state.answers[f"Question {st.session_state.current_question + 1}"] = answer

                # Move to next question
                st.session_state.current_question += 1

                # Check if all questions are answered
                if st.session_state.current_question >= len(questions):
                    st.session_state.stage = 'recommendations'

                st.rerun()
        else:
            st.warning("Unable to generate options for this question.")

    # Recommendations Stage
    elif st.session_state.stage == 'recommendations':
        st.header("🌟 Your Restaurant Recommendations")

        # Generate recommendations
        recommendations = recommender.recommend_restaurants(
            st.session_state.location_coords,
            st.session_state.answers
        )

        # Display recommendations
        st.write(recommendations)

        # Restart button
        if st.button("Start Over"):
            initialize_session_state()
            st.rerun()


if __name__ == "__main__":
    main()