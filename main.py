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

def prod_profile_scrape(username, login_choice=None, bypass_login_choice=False):
    """Scrapes an Instagram profile and returns the data"""
    profile_data = None
    top_competitor = None
    
    try:
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
            
            # Use the provided login_choice if available, otherwise ask
            if login_choice is None and not bypass_login_choice:
                print("\n=== Instagram Scraper Options ===")
                print("1. Login to Instagram manually")
                print("2. Scrape profiles (using saved login if available)")
                
                login_choice = input("\nEnter your choice (1 or 2): ")
            
            if login_choice == "1":
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
                    
            elif login_choice == "2":
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
                    output_dir = "output/product_data"
                    comp_output_dir = "output/competitor_data"

                    # Create the output directory if it doesn't exis
                    os.makedirs(output_dir, exist_ok=True)
                    os.makedirs(comp_output_dir, exist_ok=True)
                    
                    json_filename = f"{output_dir}/{username}.json"
                    with open(json_filename, 'w', encoding='utf-8') as json_file:
                        json.dump(profile_data, json_file, indent=2)
                    print(f"✅ Profile data for {username} saved to {json_filename}")
                    
                    # Find top competitor
                    print(f"Finding top competitors for {company_name}...")
                    top_competitors = get_top_competitor(company_name)
                    
                    if top_competitors:
                        print("\n=== Top Competitors Analysis ===")
                        for i, competitor in enumerate(top_competitors, 1):
                            print(f"\nCompetitor #{i}:")
                            print(f"Name: {competitor.get('competitor_name')}")
                            print(f"Instagram: {competitor.get('instagram_handle')}")
                            print(f"Followers: {competitor.get('followers_count', 0):,}")
                            print(f"Description: {competitor.get('description')}")
                            print(f"Source: {competitor.get('source')}")
                        
                        # Save competitors data to JSON file
                        competitors_json_filename = f"{comp_output_dir}/{username}_competitor.json"
                        with open(competitors_json_filename, 'w', encoding='utf-8') as json_file:
                            json.dump(top_competitors, json_file, indent=2)
                        print(f"✅ Competitors data for {username} saved to {competitors_json_filename}")
                        
                        # Still return the top competitor for backwards compatibility
                        top_competitor = top_competitors[0] if top_competitors else None
                    else:
                        print("No competitors found.")
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
    """Finds the top competitors for a given company by analyzing Instagram profile data
    and using AI-powered analysis."""
    # Check if API key is available
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ Error: Anthropic API key not found in environment variables")
        return None

    # Load competitor profile data if it exists
    competitor_data = None
    competitor_profile_path = f"output/competitor_profiles/{product_company_name}_top_competitor_*.json"
    import glob
    competitor_profiles = glob.glob(competitor_profile_path)
    
    if competitor_profiles:
        # Use the first competitor profile found
        competitor_file = competitor_profiles[0]
        try:
            with open(competitor_file, 'r', encoding='utf-8') as f:
                competitor_data = json.load(f)
            print(f"✅ Loaded competitor profile data from {competitor_file}")
        except Exception as e:
            print(f"⚠️ Warning: Failed to load competitor profile data: {str(e)}")
    
    # Load profile data of the target company to enhance our analysis
    try:
        profile_data_collection = {}
        profile_path = f"output/product_data/{product_company_name}.json"
        if os.path.exists(profile_path):
            with open(profile_path, 'r', encoding='utf-8') as f:
                profile_data_collection[product_company_name] = json.load(f)
            print(f"✅ Loaded target profile data from {profile_path}")
    except Exception as e:
        print(f"⚠️ Warning: Failed to load profile data: {str(e)}")
        profile_data_collection = {}

    # Initialize Claude client
    client = anthropic.Anthropic(api_key=api_key)

    system_message = """You are a competitive intelligence analyst specializing in social media presence.
    Find direct competitors and their Instagram metrics based on profile data provided."""

    # Prepare additional data for context
    additional_context = ""
    if profile_data_collection:
        additional_context = "Use this additional Instagram profile data for context:\n"
        for profile, data in profile_data_collection.items():
            # Extract key information for context
            followers = data.get('followers', 0)
            post_count = data.get('post_count', 0)
            post_samples = []
            
            # Get sample of post captions
            for post in data.get('posts', [])[:5]:  # Limit to 5 posts for context
                caption = post.get('caption', '').strip()
                if caption:
                    post_samples.append(caption)
            
            additional_context += f"Profile: {profile}\n"
            additional_context += f"Followers: {followers}\n"
            additional_context += f"Posts: {post_count}\n"
            additional_context += f"Sample content: {', '.join(post_samples)}\n\n"
    
    # Add competitor data context if available
    competitor_context = ""
    if competitor_data:
        competitor_context = "Use this detailed competitor profile data for analysis:\n"
        competitor_username = competitor_data.get('username', 'unknown')
        competitor_followers = competitor_data.get('followers', 0)
        competitor_following = competitor_data.get('following', 0)
        competitor_posts_count = len(competitor_data.get('posts', []))
        competitor_bio = competitor_data.get('bio', '')
        
        competitor_context += f"Competitor: {competitor_username}\n"
        competitor_context += f"Followers: {competitor_followers}\n"
        competitor_context += f"Following: {competitor_following}\n"
        competitor_context += f"Posts count: {competitor_posts_count}\n"
        competitor_context += f"Bio: {competitor_bio}\n\n"
        
        # Add sample posts from competitor
        competitor_context += "Sample competitor posts:\n"
        for post in competitor_data.get('posts', [])[:5]:
            caption = post.get('caption', '').strip()
            likes = post.get('likes', 0)
            if caption:
                competitor_context += f"- Post ({likes} likes): {caption[:100]}...\n"
        
        competitor_context += "\n"

    prompt = f"""
    Find the top 3 direct competitors for {product_company_name} in the same market segment.
    
    {additional_context}
    {competitor_context}
    
    For each competitor, include:
    - Exact company name
    - Instagram handle (full URL)
    - Estimated Instagram followers count
    - Brief description (50 words max)
    - Data source
    
    Consider the following when determining competitors:
    - Similar product/service offerings
    - Target audience overlap
    - Market positioning
    - Content strategy similarities
    
    Understand the context from the additional profile data and mostly focused on the bio understand what this compony is aobut 
            provided and use it to refine your analysis.

    
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
                return result  # Return the full list of competitors instead of just the first one
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

def comp_profile_scrape(profile_name):
    """
    Scrape the profile of the top competitor based on follower count from a competitor JSON file.
    
    Args:
        profile_name (str): Base profile name to find competitors for (without extension)
    
    Returns:
        tuple: (profile_data, None) - Profile data of the top competitor
    """
    try:
        # Construct the path to the competitor JSON file
        comp_file_path = f"output/competitor_data/{profile_name}_competitor.json"
        
        if not os.path.exists(comp_file_path):
            print(f"❌ Error: Competitor file not found at {comp_file_path}")
            return None, None
        
        # Read the competitor data from the JSON file
        with open(comp_file_path, 'r', encoding='utf-8') as file:
            competitors = json.load(file)
        
        if not competitors or not isinstance(competitors, list) or len(competitors) == 0:
            print("❌ Error: No valid competitor data found in the file")
            return None, None
        
        # Sort competitors by follower count (highest first)
        sorted_competitors = sorted(competitors, key=lambda x: x.get('followers_count', 0), reverse=True)
        
        # Initialize variables
        competitor_data = None
        
        # Try each competitor in order until one succeeds
        for comp_index, competitor in enumerate(sorted_competitors):
            if not competitor or 'instagram_handle' not in competitor:
                print(f"⚠️ Warning: Competitor #{comp_index+1} has no Instagram handle, skipping")
                continue
                
            # Extract the username from the Instagram handle URL
            instagram_url = competitor['instagram_handle']
            username = instagram_url.rstrip('/').split('/')[-1]
            
            print(f"\n=== Trying competitor #{comp_index+1} for {profile_name} ===")
            print(f"Name: {competitor.get('competitor_name')}")
            print(f"Instagram: {username}")
            print(f"Followers: {competitor.get('followers_count', 0):,}")
            
            # Use the existing function to scrape the profile, but bypass the login choice
            print(f"\n=== Scraping competitor profile: {username} ===")
            
            with sync_playwright() as playwright:
                # Create browser instance
                browser = playwright.chromium.launch(
                    headless=False,
                    slow_mo=100
                )
                
                # Create a persistent context with the user data directory 
                profile_directory = "playwright_profile"
                profile_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), profile_directory)
                
                # Check if state.json exists (saved login)
                login_state_exists = os.path.exists(os.path.join(profile_path, "state.json"))
                
                if not login_state_exists:
                    print("❌ Error: No saved login found. Please run the script first to login.")
                    return None, None
                    
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    viewport={"width": 1280, "height": 720},
                    storage_state=os.path.join(profile_path, "state.json")
                )
                
                # Create a new page
                page = context.new_page()
                
                try:
                    page.goto("https://www.instagram.com/")
                    time.sleep(3)
                    
                    # Create a dedicated directory for competitor profile images
                    # Fix: Properly format the f-string
                    competitor_image_dir = f"output/competitor_profiles/profile_images/{username}"
                    os.makedirs(competitor_image_dir, exist_ok=True)
                    
                    # Now scrape profile for the competitor username with custom image directory
                    competitor_data = scrape_profile(page, username, image_dir_override=competitor_image_dir)
                    
                    if competitor_data:
                        print(f"✅ Successfully scraped competitor profile: {username}")
                        print(f"Followers: {competitor_data['followers']}")
                        print(f"Posts: {len(competitor_data['posts'])}")
                        
                        # Save the profile data in a dedicated directory
                        output_dir = "output/competitor_profiles"
                        os.makedirs(output_dir, exist_ok=True)
                        
                        json_filename = f"{output_dir}/{profile_name}_top_competitor_{username}.json"
                        with open(json_filename, 'w', encoding='utf-8') as json_file:
                            json.dump(competitor_data, json_file, indent=2)
                        print(f"✅ Competitor profile data saved to {json_filename}")
                        
                        # If we successfully scraped this competitor, break the loop
                        browser.close()
                        print("Browser closed.")
                        return competitor_data, None
                    else:
                        print(f"⚠️ Failed to scrape competitor profile: {username}, trying next competitor if available")
                except Exception as e:
                    print(f"❌ Error during competitor scraping: {str(e)}")
                    print("Trying next competitor if available...")
                finally:
                    browser.close()
                    print("Browser closed.")
        
        # If we reached here, all competitors failed
        if len(sorted_competitors) > 0:
            print(f"❌ Failed to scrape any of the {len(sorted_competitors)} competitors")
        
        return None, None
        
    except Exception as e:
        print(f"❌ Error during competitor profile scraping: {str(e)}")
        return None, None

# If script is run directly, prompt for Instagram username
if __name__ == "__main__":
    print("\n=== Instagram Profile Analyzer ===")
    print("1. Login to Instagram")
    print("2. Analyze Instagram profile")
    
    choice = input("\nEnter your choice (1 or 2): ")
    
    if choice == "1":
        # Open Instagram login page and let user log in manually
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=False,
                slow_mo=100
            )
            
            profile_directory = "playwright_profile"
            profile_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), profile_directory)
            os.makedirs(profile_path, exist_ok=True)
            
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                viewport={"width": 1280, "height": 720}
            )
            
            page = context.new_page()
            page.goto("https://www.instagram.com/")
            
            print("\n=== Manual Login Instructions ===")
            print("1. Please log in to Instagram in the browser window that opened.")
            print("2. After successfully logging in, CLOSE THE BROWSER WINDOW manually.")
            print("3. Your login session will be saved automatically.")
            
            try:
                print("\nAfter logging in, press Enter in this console to save your session...")
                input()
                
                # Save storage state for future sessions
                context.storage_state(path=os.path.join(profile_path, "state.json"))
                print("\n✓ Login session saved.")
                print("You can now run the script with option 2 to analyze profiles.")
            except Exception as e:
                print(f"Error during manual login: {str(e)}")
            finally:
                browser.close()
                
    elif choice == "2":
        username = input("Enter the Instagram username to analyze: ")
        if not username:
            print("No username provided. Exiting.")
            exit()
            
        print("\n=== Running complete analysis workflow ===")
        print("Step 1: Scraping main profile...")
        
        # Add this line to bypass the internal prompt in scrape_profile
        login_choice = "2"  # Always use saved login
        
        # Fix: Call prod_profile_scrape instead of scrape_profile directly
        profile_data, _ = prod_profile_scrape(username, login_choice, bypass_login_choice=True)
        
        if profile_data:
            print("\nStep 2: Finding and scraping top competitor...")
            comp_data, _ = comp_profile_scrape(username)
            
            print("\n=== Analysis Complete ===")
            if comp_data:
                print("✅ Successfully analyzed profile and top competitor")
            else:
                print("⚠️ Warning: Profile analyzed but failed to analyze top competitor")
        else:
            print("❌ Failed to analyze profile. Workflow stopped.")
    else:
        print("Invalid choice.")
    

