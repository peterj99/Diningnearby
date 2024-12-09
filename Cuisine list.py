import os
import requests
import pandas as pd
from dotenv import load_dotenv
from collections import Counter
import time

# Load environment variables
load_dotenv()


class GooglePlacesRestaurantAnalyzer:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        self.details_url = "https://maps.googleapis.com/maps/api/place/details/json"
        self.restaurants = []

    def _extract_cuisine_types(self, details):
        """
        Extract cuisine types from restaurant details
        """
        cuisine_types = []

        # Check different possible sources for cuisine information
        if 'types' in details:
            cuisine_types.extend([
                t.replace('_', ' ').title()
                for t in details['types']
                if t in ['restaurant', 'food', 'meal_takeaway', 'meal_delivery']
            ])

        # Extract from editorial summary or reviews if available
        if 'editorial_summary' in details and details['editorial_summary']:
            cuisine_types.append(details['editorial_summary'].get('language', 'Unknown'))

        return cuisine_types if cuisine_types else ['Unknown']

    def fetch_restaurants_in_location(self, latitude, longitude, radius=50000, max_results=1000):
        """
        Fetch restaurants near a specific location
        """
        restaurants_found = 0
        next_page_token = None

        while restaurants_found < max_results:
            params = {
                'location': f"{latitude},{longitude}",
                'radius': radius,
                'type': 'restaurant',
                'key': self.api_key
            }

            # Add next page token if available
            if next_page_token:
                params['pagetoken'] = next_page_token

            try:
                response = requests.get(self.base_url, params=params)
                data = response.json()

                if data['status'] != 'OK':
                    print(f"Error fetching restaurants: {data.get('status', 'Unknown error')}")
                    break

                # Fetch detailed information for each restaurant
                for place in data.get('results', []):
                    if restaurants_found >= max_results:
                        break

                    # Get place details
                    details_params = {
                        'place_id': place['place_id'],
                        'key': self.api_key,
                        'fields': 'name,types,editorial_summary'
                    }
                    details_response = requests.get(self.details_url, params=details_params)
                    details_data = details_response.json()

                    if details_data['status'] == 'OK':
                        place_details = details_data.get('result', {})
                        cuisine_types = self._extract_cuisine_types(place_details)

                        self.restaurants.append({
                            'name': place_details.get('name', 'Unknown'),
                            'cuisine_types': cuisine_types
                        })
                        restaurants_found += 1

                # Check for next page token
                next_page_token = data.get('next_page_token')
                if not next_page_token:
                    break

                # Wait for page token to be valid
                time.sleep(2)

            except Exception as e:
                print(f"An error occurred: {e}")
                break

        return self.restaurants

    def analyze_cuisine_types(self, top_n=50):
        """
        Analyze and return top cuisine types
        """
        # Flatten cuisine types
        all_cuisines = [
            cuisine
            for restaurant in self.restaurants
            for cuisine in restaurant['cuisine_types']
        ]

        # Count and return top cuisines
        cuisine_counts = Counter(all_cuisines)
        return cuisine_counts.most_common(top_n)


def main():
    # Retrieve API key from environment variable
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")

    if not api_key:
        raise ValueError("No API key found. Please set GOOGLE_PLACES_API_KEY in your .env file.")

    # Major US cities for comprehensive coverage
    us_locations = [
        # Major city coordinates (latitude, longitude)
        (40.7128, -74.0060),  # New York City
        (34.0522, -118.2437),  # Los Angeles
        (41.8781, -87.6298),  # Chicago
        (29.7604, -95.3698),  # Houston
        (33.4484, -112.0740),  # Phoenix
        (39.9526, -75.1652),  # Philadelphia
        (38.9072, -77.0369),  # Washington D.C.
        (29.4241, -98.4936),  # San Antonio
        (32.7767, -96.7970),  # Dallas
        (37.7749, -122.4194)  # San Francisco
    ]

    analyzer = GooglePlacesRestaurantAnalyzer(api_key)

    # Collect restaurants from multiple locations
    for lat, lon in us_locations:
        analyzer.fetch_restaurants_in_location(lat, lon, max_results=1000)

    # Analyze cuisine types
    top_cuisines = analyzer.analyze_cuisine_types(top_n=50)

    # Print results
    print("\n--- Top 50 Cuisine Types Across US ---")
    for cuisine, count in top_cuisines:
        print(f"{cuisine}: {count} restaurants")

    # Optional: Save results to CSV
    cuisine_df = pd.DataFrame(top_cuisines, columns=['Cuisine Type', 'Count'])
    cuisine_df.to_csv('top_us_restaurant_cuisines.csv', index=False)


if __name__ == "__main__":
    main()