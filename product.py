from insta_scraper import login_to_instagram, scrape_profile, driver
import json
import os
import anthropic
from dotenv import load_dotenv
api_key = os.getenv("ANTHROPIC_API_KEY")
# Load environment variables from .env file
load_dotenv()
def prod_profile_scrape(username):
    try:
        if not username:
            print("No username provided. Exiting.")
            return
            
        print(f"Starting analysis for Instagram profile: {username}")
        
        # Login to Instagram
        print("Logging in to Instagram...")
        if not login_to_instagram():
            print("Failed to login. Exiting.")
            driver.quit()
            exit(1)
        
        # Scrape the profile
        print(f"Scraping profile data for {username}...")
        profile_data = scrape_profile(username)
        
        if profile_data:
            print(f"✅ Successfully scraped profile: {username}")
            print(f"Followers: {profile_data['followers']}")
            print(f"Posts: {len(profile_data['posts'])}")
            
            # Get company name from profile data if available, otherwise use username
            company_name = profile_data.get("real_name", username)
            
            # Save profile data to JSON file
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = "e:/audit-ai-automation-main-insta-extension/profile_data"
            os.makedirs(output_dir, exist_ok=True)
            
            json_filename = f"{output_dir}/profile_data_{username}_{timestamp}.json"
            with open(json_filename, 'w', encoding='utf-8') as json_file:
                json.dump(profile_data, json_file, indent=2)
            print(f"✅ Profile data for {username} saved to {json_filename}")
            
            # Find top competitor
            print(f"Finding top competitors for {company_name}...")
            top_competitor = get_top_competitor(company_name)
            
            if top_competitor:
                print("\n=== Top Competitor Analysis ===")
                print(f"Competitor Name: {top_competitor.get('competitor_name')}")
                print(f"Instagram Handle: {top_competitor.get('instagram_handle')}")
                print(f"Followers Count: {top_competitor.get('followers_count'):,}")
                print(f"Description: {top_competitor.get('description')}")
                print(f"Source: {top_competitor.get('source')}")
            else:
                print("No competitors found.")
                
            return profile_data, top_competitor
        else:
            print(f"Failed to scrape profile: {username}")
            return None, None
            
    except Exception as e:
        print(f"❌ Error during execution: {str(e)}")
        return None, None
    finally:
        # Close the browser
        driver.quit()

def get_top_competitor(product_company_name):
    # Check if API key is available
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ Error: Anthropic API key not found in environment variables")
        return None

    # Initialize Claude client
    client = anthropic.Anthropic(api_key=api_key)

    system_message = "You are a competitive intelligence analyst specializing in social media presence. Find direct competitors and their Instagram metrics."

    prompt = f"""
    Find the top 3 direct competitors for {product_company_name} in the same market segment. For each competitor, include:
    - Exact company name
    - Instagram handle (full URL)
    - Estimated Instagram followers count
    - Brief description (50 words max)
    - Data source
    Return ONLY a valid JSON array sorted by followers_count (highest first). Example:
    [
    {{
      "competitor_name": "Example Inc",
      "instagram_handle": "https://www.instagram.com/example/",
      "followers_count": 1500000,
      "description": "Leading provider of...",
      "source": "Instagram API 2023"
    }}
    ]
    """

    try:
        response = client.messages.create(
            model="claude-3-opus-20240229",
            system=system_message,
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        raw_text = response.content[0].text.strip()
        
        # Extract JSON from response - find where the JSON array starts and ends
        try:
            json_start = raw_text.find('[')
            json_end = raw_text.rfind(']') + 1
            
            if json_start >= 0 and json_end > json_start:
                raw_json = raw_text[json_start:json_end]
                result = json.loads(raw_json)
                return result[0] if result else None
            else:
                print("❌ Error: Could not find JSON array in Claude's response")
                print("🔍 Raw response content:")
                print(raw_text)
                return None
        except Exception as e:
            print(f"❌ Error: Failed to extract JSON from response: {e}")
            print("🔍 Raw response content:")
            print(raw_text)
            return None

    except json.JSONDecodeError as e:
        print(f"❌ Error: Failed to parse Claude response as JSON: {e}")
        print("🔍 Raw response content:")
        print(raw_text)
        return None
    except Exception as e:
        print(f"❌ Error getting competitors: {e}")
        return None
# Update the main block to properly call the function with a username parameter
if __name__ == "__main__":
    username = "tamaranashik"
    #username = input("Enter the Instagram username to analyze: ")
    prod_profile_scrape(username)

