from insta_scraper_playwright import login_to_instagram, scrape_profile
import json
import os
import anthropic
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
import time

# Load environment variables from .env file
load_dotenv()
api_key = os.getenv("ANTHROPIC_API_KEY")

def prod_profile_scrape(username):
    profile_data = None
    top_competitor = None
    
    try:
        # Display options to the user
        print("\n=== Instagram Scraper Options ===")
        print("1. Login to Instagram manually")
        print("2. Scrape profiles (using saved login if available)")
        
        choice = input("\nEnter your choice (1 or 2): ")
        
        with sync_playwright() as playwright:
            # Create browser instance
            browser = playwright.chromium.launch(
                headless=False,  # Set to True for production
                slow_mo=100  # Slows down Playwright operations to make them visible
            )
            
            # Create a persistent context with the user data directory 
            profile_directory = "playwright_profile"
            profile_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), profile_directory)
            os.makedirs(profile_path, exist_ok=True)
            
            # Check if state.json exists (saved login)
            login_state_exists = os.path.exists(os.path.join(profile_path, "state.json"))
            
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                viewport={"width": 1280, "height": 720},
                storage_state=os.path.join(profile_path, "state.json") if login_state_exists else None
            )
            
            # Create a new page
            page = context.new_page()
            
            if choice == "1":
                # Open Instagram login page and let user log in manually
                page.goto("https://www.instagram.com/")
                
                print("\n=== Manual Login Instructions ===")
                print("1. Please log in to Instagram in the browser window that opened.")
                print("2. After successfully logging in, CLOSE THE BROWSER WINDOW manually.")
                print("3. Your login session will be saved automatically.")
                
                try:
                    # Wait for user to manually close the browser or press Enter to continue
                    print("\nAfter logging in, press Enter in this console to save your session...")
                    input()
                    
                    # Save storage state for future sessions
                    context.storage_state(path=os.path.join(profile_path, "state.json"))
                    print("\n✓ Login session saved.")
                    print("You can now run the scraper with option 2 to scrape profiles.")
                except Exception as e:
                    print(f"Error during manual login: {str(e)}")
                    
            elif choice == "2":
                # Check if we need to login first
                login_needed = not login_state_exists
                
                if login_needed:
                    print("No saved login found. Logging in first...")
                    if not login_to_instagram(page):
                        print("Failed to login. Exiting.")
                        browser.close()
                        return None, None
                    
                    # Save storage state for future sessions
                    context.storage_state(path=os.path.join(profile_path, "state.json"))
                else:
                    # Try to use the saved login
                    try:
                        page.goto("https://www.instagram.com/")
                        time.sleep(3)
                        
                        # Check if we're still logged in
                        logged_in = page.locator(
                            "div[role='button'][aria-label*='Profile'], span[aria-label*='Profile'], a[href*='/direct/inbox/']"
                        ).count() > 0
                        
                        if not logged_in:
                            print("Saved login expired. Logging in again...")
                            if not login_to_instagram(page):
                                print("Failed to login. Exiting.")
                                browser.close()
                                return None, None
                            
                            # Save storage state for future sessions
                            context.storage_state(path=os.path.join(profile_path, "state.json"))
                        else:
                            print("Using saved login session.")
                    except Exception as e:
                        print(f"Error checking login status: {str(e)}")
                        print("Attempting to login again...")
                        if not login_to_instagram(page):
                            print("Failed to login. Exiting.")
                            browser.close()
                            return None, None
                
                # Now scrape profile for the given username
                if not username:
                    print("No username provided. Exiting.")
                    browser.close()
                    return None, None
                    
                print(f"\n=== Starting to scrape profile for: {username} ===")
                profile_data = scrape_profile(page, username)
                
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
                    print(f"Failed to scrape profile: {username}")
            
            # Close the browser
            browser.close()
            print("Browser closed.")
            
    except Exception as e:
        print(f"❌ Error during execution: {str(e)}")
        return None, None
        
    return profile_data, top_competitor

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

# If script is run directly, prompt for Instagram username
if __name__ == "__main__":
    username = input("Enter the Instagram username to analyze: ")
    prod_profile_scrape(username)

