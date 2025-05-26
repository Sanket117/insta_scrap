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
                    print(f"Successfully scraped profile: {username}")
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
                    print(f"Profile data for {username} saved to {json_filename}")
                    
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
                        print(f"Competitors data for {username} saved to {competitors_json_filename}")
                        
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
        print(f"Error during execution: {str(e)}")
        return None, None
        
    return profile_data, top_competitor

def get_top_competitor(product_company_name):
    """Finds the top competitors for a given company by analyzing Instagram profile data
    and using AI-powered analysis. Always includes at least one reliable competitor that exists on Instagram."""
    # Check if API key is available
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: Anthropic API key not found in environment variables")
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
            print(f"Loaded competitor profile data from {competitor_file}")
        except Exception as e:
            print(f"Warning: Failed to load competitor profile data: {str(e)}")
    
    # Load profile data of the target company to enhance our analysis
    try:
        profile_data_collection = {}
        profile_path = f"output/product_data/{product_company_name}.json"
        if os.path.exists(profile_path):
            with open(profile_path, 'r', encoding='utf-8') as f:
                profile_data_collection[product_company_name] = json.load(f)
            print(f"✅ Loaded target profile data from {profile_path}")
        
            # Try to determine the business sector from the loaded profile data
            company_bio = profile_data_collection[product_company_name].get('bio', '')
            company_name = profile_data_collection[product_company_name].get('real_name', product_company_name)
        else:
            company_bio = ""
            company_name = product_company_name
    except Exception as e:
        print(f"⚠️ Warning: Failed to load profile data: {str(e)}")
        profile_data_collection = {}
        company_bio = ""
        company_name = product_company_name

    # Initialize Claude client
    client = anthropic.Anthropic(api_key=api_key)

    system_message = """You are a competitive intelligence analyst specializing in social media presence.
    Find direct competitors and their Instagram metrics based on profile data provided.
    You MUST include at least one reliable competitor that definitely exists on Instagram."""

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

    # Determine likely business sector from bio and other information
    sector_analysis_prompt = f"""
    Based on this company information, determine the most likely business sector:
    
    Company Name: {company_name}
    Company Bio: {company_bio}
    
    Return ONLY the business sector or industry name as a single word or short phrase. For example:
    "Finance", "Fashion", "Food & Beverage", "Technology", "Health & Fitness", etc.
    """
    
    try:
        sector_response = client.messages.create(
            model="claude-3-haiku-20240307",
            system="You are a business sector analyst. Determine the business sector based on the company information.",
            max_tokens=50,
            messages=[
                {"role": "user", "content": sector_analysis_prompt}
            ]
        )
        
        business_sector = sector_response.content[0].text.strip().replace('"', '').replace("'", "")
        print(f"Detected business sector: {business_sector}")
    except Exception as e:
        print(f"Warning: Failed to determine business sector: {str(e)}")
        business_sector = "Unknown"

    # Define reliable fallback competitors by sector
    reliable_competitors = {
        "Finance": [
            {
                "competitor_name": "Chase Bank",
                "instagram_handle": "https://www.instagram.com/chase/",
                "followers_count": 500000,
                "description": "Major financial institution offering banking, investment, and loan services.",
                "source": "Fallback competitor data",
                "is_fallback": True
            }
        ],
        "Fashion": [
            {
                "competitor_name": "H&M",
                "instagram_handle": "https://www.instagram.com/hm/", 
                "followers_count": 38000000,
                "description": "Global fashion retailer offering trendy clothing and accessories.",
                "source": "Fallback competitor data",
                "is_fallback": True
            }
        ],
        "Food & Beverage": [
            {
                "competitor_name": "Starbucks",
                "instagram_handle": "https://www.instagram.com/starbucks/",
                "followers_count": 18000000,
                "description": "International coffeehouse chain with premium coffee and food offerings.",
                "source": "Fallback competitor data",
                "is_fallback": True
            }
        ],
        "Technology": [
            {
                "competitor_name": "Microsoft",
                "instagram_handle": "https://www.instagram.com/microsoft/",
                "followers_count": 4000000,
                "description": "Technology company providing hardware, software, and cloud solutions.",
                "source": "Fallback competitor data",
                "is_fallback": True
            }
        ],
        "Health & Fitness": [
            {
                "competitor_name": "Nike",
                "instagram_handle": "https://www.instagram.com/nike/",
                "followers_count": 270000000,
                "description": "Athletic apparel and fitness equipment company.",
                "source": "Fallback competitor data",
                "is_fallback": True
            }
        ],
        "Beauty & Cosmetics": [
            {
                "competitor_name": "Sephora",
                "instagram_handle": "https://www.instagram.com/sephora/",
                "followers_count": 21000000,
                "description": "Global beauty retailer offering cosmetics, skincare, and fragrance products.",
                "source": "Fallback competitor data",
                "is_fallback": True
            }
        ],
        "Entertainment": [
            {
                "competitor_name": "Netflix",
                "instagram_handle": "https://www.instagram.com/netflix/",
                "followers_count": 32000000,
                "description": "Streaming service offering movies, TV shows and original content.",
                "source": "Fallback competitor data",
                "is_fallback": True
            }
        ],
        "Unknown": [
            {
                "competitor_name": "Forbes",
                "instagram_handle": "https://www.instagram.com/forbes/",
                "followers_count": 8000000,
                "description": "Global media company focusing on business, investing, technology, and leadership.",
                "source": "Fallback competitor data",
                "is_fallback": True
            }
        ]
    }

    prompt = f"""
    Find the top 3 direct competitors for {product_company_name} in the same market segment.
    
    {additional_context}
    {competitor_context}
    
    I've determined this company is likely in the {business_sector} sector.
    
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
    
    IMPORTANT: You MUST include at least one competitor that definitely exists on Instagram.
    These should be well-known brands that definitely have an Instagram presence.

    Understand the context from the additional profile data and mostly focused on the bio understand what this company is about 
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
                competitors = json.loads(raw_json)
                
                # Check if competitors were found
                if not competitors or len(competitors) == 0:
                    print("No competitors found from AI, adding fallback competitor")
                    # Add a fallback competitor based on sector
                    sector_to_use = business_sector if business_sector in reliable_competitors else "Unknown"
                    competitors = reliable_competitors[sector_to_use]
                else:
                    # Always add one reliable competitor as the last item
                    # to ensure we have at least one that exists on Instagram
                    sector_to_use = business_sector if business_sector in reliable_competitors else "Unknown"
                    fallback = reliable_competitors[sector_to_use][0]
                    
                    # Check if fallback is already in the list
                    fallback_already_included = False
                    for comp in competitors:
                        if comp.get('instagram_handle', '').lower() == fallback['instagram_handle'].lower():
                            fallback_already_included = True
                            break
                    
                    if not fallback_already_included:
                        competitors.append(fallback)
                
                # Sort by followers count
                sorted_competitors = sorted(competitors, key=lambda x: x.get('followers_count', 0), reverse=True)
                
                print(f"Found {len(sorted_competitors)} competitors (including fallbacks if needed)")
                for i, comp in enumerate(sorted_competitors, 1):
                    print(f"Competitor #{i}: {comp.get('competitor_name')} - {comp.get('instagram_handle')}")
                
                return sorted_competitors
            else:
                print("Error: Could not find JSON array in Claude's response")
                print("🔍 Raw response content:")
                print(raw_text)
                # Use fallback
                sector_to_use = business_sector if business_sector in reliable_competitors else "Unknown"
                return reliable_competitors[sector_to_use]
        except Exception as e:
            print(f"Error: Failed to extract JSON from response: {e}")
            print("🔍 Raw response content:")
            print(raw_text)
            # Use fallback
            sector_to_use = business_sector if business_sector in reliable_competitors else "Unknown"
            return reliable_competitors[sector_to_use]

    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse Claude response as JSON: {e}")
        print("🔍 Raw response content:")
        print(raw_text)
        # Use fallback
        sector_to_use = business_sector if business_sector in reliable_competitors else "Unknown"
        return reliable_competitors[sector_to_use]
    except Exception as e:
        print(f"Error getting competitors: {e}")
        # Use fallback
        sector_to_use = business_sector if business_sector in reliable_competitors else "Unknown"
        return reliable_competitors[sector_to_use]

def comp_profile_scrape(profile_name):
    """
    Scrape the profile of the top competitor based on follower count from a competitor JSON file.
    If the Instagram username can't be accessed, falls back to a reliable competitor in the same sector.
    
    Args:
        profile_name (str): Base profile name to find competitors for (without extension)
    
    Returns:
        tuple: (profile_data, None) - Profile data of the top competitor
    """
    try:
        # Construct the path to the competitor JSON file
        comp_file_path = f"output/competitor_data/{profile_name}_competitor.json"
        
        # Load product company data to determine sector if needed
        product_data_path = f"output/product_data/{profile_name}.json"
        business_sector = "Unknown"
        
        if os.path.exists(product_data_path):
            try:
                with open(product_data_path, 'r', encoding='utf-8') as file:
                    product_data = json.load(file)
                    
                # Use product data to determine the business sector if needed for fallback
                product_bio = product_data.get('bio', '')
                product_name = product_data.get('real_name', profile_name)
                
                # Initialize Claude client for sector analysis if needed
                api_key = os.getenv("ANTHROPIC_API_KEY")
                if api_key:
                    client = anthropic.Anthropic(api_key=api_key)
                    
                    sector_analysis_prompt = f"""
                    Based on this company information, determine the most likely business sector:
                    
                    Company Name: {product_name}
                    Company Bio: {product_bio}
                    
                    Return ONLY the business sector or industry name as a single word or short phrase. For example:
                    "Finance", "Fashion", "Food & Beverage", "Technology", "Health & Fitness", etc.
                    """
                    
                    try:
                        sector_response = client.messages.create(
                            model="claude-3-haiku-20240307",
                            system="You are a business sector analyst. Determine the business sector based on the company information.",
                            max_tokens=50,
                            messages=[
                                {"role": "user", "content": sector_analysis_prompt}
                            ]
                        )
                        
                        business_sector = sector_response.content[0].text.strip().replace('"', '').replace("'", "")
                        print(f"Detected business sector: {business_sector}")
                    except Exception as e:
                        print(f"Warning: Failed to determine business sector: {str(e)}")
            except Exception as e:
                print(f"Warning: Failed to analyze product data for sector: {str(e)}")
        
        # Define reliable fallback competitors by sector
        reliable_competitors = {
            "Finance": {
                "name": "Chase Bank",
                "username": "chase" 
            },
            "Fashion": {
                "name": "H&M",
                "username": "hm"
            },
            "Food & Beverage": {
                "name": "Starbucks",
                "username": "starbucks"
            },
            "Technology": {
                "name": "Microsoft",
                "username": "microsoft"
            },
            "Health & Fitness": {
                "name": "Nike",
                "username": "nike"
            },
            "Beauty & Cosmetics": {
                "name": "Sephora",
                "username": "sephora"
            },
            "Entertainment": {
                "name": "Netflix",
                "username": "netflix"
            },
            "Unknown": {
                "name": "Forbes",
                "username": "forbes"
            }
        }
        
        # Try to get competitor from the competitor JSON file first
        if os.path.exists(comp_file_path):
            # Read the competitor data from the JSON file
            with open(comp_file_path, 'r', encoding='utf-8') as file:
                competitors = json.load(file)
            
            if competitors and isinstance(competitors, list) and len(competitors) > 0:
                # Sort competitors by follower count (highest first)
                sorted_competitors = sorted(competitors, key=lambda x: x.get('followers_count', 0), reverse=True)
                
                # Try each competitor in order until one succeeds
                for comp_index, competitor in enumerate(sorted_competitors):
                    if not competitor or 'instagram_handle' not in competitor:
                        print(f"Warning: Competitor #{comp_index+1} has no Instagram handle, skipping")
                        continue
                        
                    # Extract the username from the Instagram handle URL
                    instagram_url = competitor['instagram_handle']
                    username = instagram_url.rstrip('/').split('/')[-1]
                    
                    print(f"\n=== Trying competitor #{comp_index+1} for {profile_name} ===")
                    print(f"Name: {competitor.get('competitor_name')}")
                    print(f"Instagram: {username}")
                    print(f"Followers: {competitor.get('followers_count', 0):,}")
                    
                    # Try scraping this competitor
                    competitor_data = scrape_competitor_profile(username, profile_name)
                    
                    if competitor_data:
                        print(f"Successfully scraped competitor profile: {username}")
                        return competitor_data, None
        else:
            print(f"Competitor file not found at {comp_file_path}")
        
        # If we reached here, either no competitor file exists or all competitors failed
        # Use fallback competitor based on detected sector
        print("\n=== Using reliable fallback competitor based on business sector ===")
        
        fallback_sector = business_sector if business_sector in reliable_competitors else "Unknown"
        fallback_competitor = reliable_competitors[fallback_sector]
        
        print(f"Business sector: {fallback_sector}")
        print(f"Fallback competitor: {fallback_competitor['name']} (@{fallback_competitor['username']})")
        
        # Try scraping the fallback competitor
        fallback_data = scrape_competitor_profile(fallback_competitor['username'], profile_name)
        
        if fallback_data:
            print(f"Successfully scraped fallback competitor: {fallback_competitor['username']}")
            return fallback_data, None
        
        # If all attempts fail, try a last-resort competitor: Forbes
        if fallback_sector != "Unknown":
            print("\n=== Trying last-resort competitor: Forbes ===")
            last_resort_data = scrape_competitor_profile("forbes", profile_name)
            
            if last_resort_data:
                print("Successfully scraped last-resort competitor: forbes")
                return last_resort_data, None
        
        print("Failed to scrape any competitor, including fallbacks")
        return None, None
        
    except Exception as e:
        print(f"Error during competitor profile scraping: {str(e)}")
        return None, None

def scrape_competitor_profile(username, profile_name):
    """Helper function to scrape a competitor profile"""
    try:
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
                print("Error: No saved login found. Please run the script first to login.")
                return None
                
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
                competitor_image_dir = f"output/competitor_profiles/profile_images/{username}"
                os.makedirs(competitor_image_dir, exist_ok=True)
                
                # Now scrape profile for the competitor username with custom image directory
                competitor_data = scrape_profile(page, username, image_dir_override=competitor_image_dir)
                
                if competitor_data:
                    print(f"Successfully scraped competitor profile: {username}")
                    print(f"Followers: {competitor_data['followers']}")
                    print(f"Posts: {len(competitor_data['posts'])}")
                    
                    # Save the profile data in a dedicated directory
                    output_dir = "output/competitor_profiles"
                    os.makedirs(output_dir, exist_ok=True)
                    
                    json_filename = f"{output_dir}/{profile_name}_top_competitor_{username}.json"
                    with open(json_filename, 'w', encoding='utf-8') as json_file:
                        json.dump(competitor_data, json_file, indent=2)
                    print(f"Competitor profile data saved to {json_filename}")
                    
                    return competitor_data
                else:
                    print(f"⚠️ Failed to scrape competitor profile: {username}")
                    return None
            except Exception as e:
                print(f"Error during competitor scraping: {str(e)}")
                return None
            finally:
                browser.close()
                print("Browser closed.")
    except Exception as e:
        print(f"Error during competitor scraping: {str(e)}")
        return None

def generate_company_descriptions(profile_name):
    """
    Generate simple descriptions for both the product company and its top competitor
    using Claude AI. Saves results to JSON files.
    
    Args:
        profile_name (str): Instagram username of the product company
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Check if API key is available
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("Error: Anthropic API key not found in environment variables")
            return False
            
        # Create output directory
        output_dir = "output/descriptions"
        os.makedirs(output_dir, exist_ok=True)
        
        # Load product company data
        product_data_path = f"output/product_data/{profile_name}.json"
        if not os.path.exists(product_data_path):
            print(f"Error: Product data not found at {product_data_path}")
            return False
            
        with open(product_data_path, 'r', encoding='utf-8') as file:
            product_data = json.load(file)
            
        # Find competitor data file
        competitor_json_path = f"output/competitor_data/{profile_name}_competitor.json"
        if not os.path.exists(competitor_json_path):
            print(f"Error: Competitor data not found at {competitor_json_path}")
            return False
            
        with open(competitor_json_path, 'r', encoding='utf-8') as file:
            competitors = json.load(file)
            
        # Get top competitor
        if not competitors or not isinstance(competitors, list) or len(competitors) == 0:
            print("Error: No valid competitor data found in the file")
            return False
            
        top_competitor = max(competitors, key=lambda x: x.get('followers_count', 0))
        competitor_handle = top_competitor.get('instagram_handle', '').rstrip('/').split('/')[-1]
        
        # Load competitor profile data if available
        competitor_profile_path = f"output/competitor_profiles/{profile_name}_top_competitor_{competitor_handle}.json"
        competitor_profile_data = None
        
        if os.path.exists(competitor_profile_path):
            with open(competitor_profile_path, 'r', encoding='utf-8') as file:
                competitor_profile_data = json.load(file)
                
        # Initialize Claude client
        client = anthropic.Anthropic(api_key=api_key)
        
        # Generate simple product company description
        print(f"\n=== Generating simple description for {profile_name} ===")
        
        product_system_message = """You are a business analyst specializing in social media marketing.
        Provide a brief company description based on Instagram profile data."""
        
        # Extract data for product company
        product_bio = product_data.get('bio', '')
        product_followers = product_data.get('followers', 0)
        product_name = product_data.get('real_name', profile_name)
        
        product_prompt = f"""
        Create a simple 2-3 line business description for {product_name} (@{profile_name}) based on their Instagram profile.
        
        Instagram Profile Data:
        - Username: {profile_name}
        - Full Name: {product_name}
        - Bio: {product_bio}
        - Followers: {product_followers:,}
        
        Format the response as a JSON object with these fields:
        - company_name: The company name
        - company_handle: Instagram handle
        - brief_description: A 2-3 line description of what the company does
        
        Return ONLY valid JSON with no additional text.
        """
        
        try:
            product_response = client.messages.create(
                model="claude-3-opus-20240229",
                system=product_system_message,
                max_tokens=500,
                messages=[
                    {"role": "user", "content": product_prompt}
                ]
            )
            
            product_raw_text = product_response.content[0].text.strip()
            
            # Extract JSON from response
            product_json_start = product_raw_text.find('{')
            product_json_end = product_raw_text.rfind('}') + 1
            
            if product_json_start >= 0 and product_json_end > product_json_start:
                product_raw_json = product_raw_text[product_json_start:product_json_end]
                product_description = json.loads(product_raw_json)
                
                # Save product description
                product_desc_path = f"{output_dir}/{profile_name}_description.json"
                with open(product_desc_path, 'w', encoding='utf-8') as file:
                    json.dump(product_description, file, indent=2)
                print(f"✅ Product company description saved to {product_desc_path}")
            else:
                print("Error: Could not find JSON in Claude's product company response")
                print(product_raw_text)
                return False
                
        except Exception as e:
            print(f"Error generating product description: {e}")
            return False
            
        # Generate simple competitor description if data is available
        if competitor_profile_data:
            print(f"\n=== Generating simple description for competitor {competitor_handle} ===")
            
            competitor_system_message = """You are a competitive intelligence analyst.
            Provide a brief company description based on Instagram profile data."""
            
            # Extract data for competitor
            competitor_bio = competitor_profile_data.get('bio', '')
            competitor_followers = competitor_profile_data.get('followers', 0)
            competitor_name = competitor_profile_data.get('real_name', competitor_handle)
            
            competitor_prompt = f"""
            Create a simple 2-3 line business description for {competitor_name} (@{competitor_handle}) based on their Instagram profile.
            
            Instagram Profile Data:
            - Username: {competitor_handle}
            - Full Name: {competitor_name}
            - Bio: {competitor_bio}
            - Followers: {competitor_followers:,}
            
            Format the response as a JSON object with these fields:
            - company_name: The company name
            - company_handle: Instagram handle
            - brief_description: A 2-3 line description of what the company does
            
            Return ONLY valid JSON with no additional text.
            """
            
            try:
                competitor_response = client.messages.create(
                    model="claude-3-opus-20240229",
                    system=competitor_system_message,
                    max_tokens=500,
                    messages=[
                        {"role": "user", "content": competitor_prompt}
                    ]
                )
                
                competitor_raw_text = competitor_response.content[0].text.strip()
                
                # Extract JSON from response
                competitor_json_start = competitor_raw_text.find('{')
                competitor_json_end = competitor_raw_text.rfind('}') + 1
                
                if competitor_json_start >= 0 and competitor_json_end > competitor_json_start:
                    competitor_raw_json = competitor_raw_text[competitor_json_start:competitor_json_end]
                    competitor_description = json.loads(competitor_raw_json)
                    
                    # Save competitor description
                    competitor_desc_path = f"{output_dir}/{profile_name}_competitor_{competitor_handle}_description.json"
                    with open(competitor_desc_path, 'w', encoding='utf-8') as file:
                        json.dump(competitor_description, file, indent=2)
                    print(f"✅ Competitor description saved to {competitor_desc_path}")
                else:
                    print("Error: Could not find JSON in Claude's competitor response")
                    print(competitor_raw_text)
                    return False
                    
            except Exception as e:
                print(f"Error generating competitor description: {e}")
                return False
        else:
            print(f"Note: Competitor profile data not available for description")
            
        return True
            
    except Exception as e:
        print(f"Error during description generation: {str(e)}")
        return False

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
            
            if comp_data:
                print("\nStep 3: Generating company descriptions and analysis...")
                desc_success = generate_company_descriptions(username)
                
                print("\n=== Analysis Complete ===")
                if desc_success:
                    print("✅ Successfully analyzed profile, top competitor, and generated descriptions")
                else:
                    print("⚠️ Warning: Profile and competitor analyzed but description generation failed")
            else:
                print("\n=== Analysis Complete ===")
                print("⚠️ Warning: Profile analyzed but failed to analyze top competitor")
        else:
            print("❌ Failed to analyze profile. Workflow stopped.")
    else:
        print("Invalid choice.")
    

