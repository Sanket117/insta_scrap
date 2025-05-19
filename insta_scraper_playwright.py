from playwright.sync_api import sync_playwright
import json
import os
import time
import requests
from datetime import datetime
import urllib.parse
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
# Login credentials from environment variables
username = os.getenv('INSTAGRAM_USERNAME')
password = os.getenv('INSTAGRAM_PASSWORD')

# Check if environment variables are set
if not username or not password:
    raise ValueError("INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD environment variables must be set")

# Users to scrape
users = [
    'snapchat',
    # Add more users as needed
]

# Setup directories
output_dir = "E:/audit-ai-automation-main-insta-extension/profile_data"
os.makedirs(output_dir, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
image_dir = f"{output_dir}/profile_images_{timestamp}"
os.makedirs(image_dir, exist_ok=True)

# Function to handle login
def login_to_instagram(page):
    page.goto("https://www.instagram.com/")
    time.sleep(3)
    
    # Check if already logged in by looking for profile icon or other elements present after login
    try:
        logged_in_check = page.wait_for_selector(
            "div[role='button'][aria-label*='Profile'], span[aria-label*='Profile'], a[href*='/direct/inbox/']",
            timeout=5000
        )
        print("### Already logged in! Session loaded successfully.")
        return True
    except:
        print("### Not logged in. Proceeding with login...")
    
    # Handle cookies popup if it appears
    try:
        cookie_button = page.wait_for_selector(
            "button:has-text('Accept'), button:has-text('Allow')",
            timeout=5000
        )
        cookie_button.click()
        print("### Cookies: Accept [x]")
        time.sleep(2)
    except:
        print("### Cookies window not found. Skipping to login..")
    
    # Enter username and password
    print("### Entering in Instagram Username and Password..")
    try:
        username_field = page.wait_for_selector("input[name='username']", timeout=10000)
        password_field = page.locator("input[name='password']")
        
        username_field.fill(username)
        password_field.fill(password)
        
        login_button = page.locator("button[type='submit']")
        login_button.click()
        time.sleep(5)
    except Exception as e:
        print(f"Error during login: {str(e)}")
        return False
    
    # Handle "Save Login Info" popup
    try:
        not_now_button = page.wait_for_selector("button:has-text('Not Now')", timeout=5000)
        not_now_button.click()
        print("### Save Login Info: Not Now [x]")
        time.sleep(2)
    except:
        print("Save Login Info popup not found. Skipping..")
    
    # Handle "Notifications" popup
    try:
        not_now_button = page.wait_for_selector("button:has-text('Not Now')", timeout=5000)
        not_now_button.click()
        print("### Notifications: Not Now [x]")
        time.sleep(2)
    except:
        print("Notifications popup not found. Skipping..")
    
    return True

# Function to scrape profile data
def scrape_profile(page, username):
    profile_data = {
        "username": username,
        "private": False,
        "verified": False,
        "real_name": "",
        "website": "",
        "bio": "",
        "post_count": 0,
        "followers": 0,
        "following": 0,
        "posts": []  # Will store information about the latest posts
    }
    
    try:
        # Go to the user's profile
        page.goto(f"https://www.instagram.com/{username}/")
        time.sleep(5)
        
        # Check if profile exists
        if "Page Not Found" in page.title() or "Sorry, this page isn't available." in page.content():
            print(f"Profile not found: {username}")
            return None
        
        # Extract profile data using modern selectors
        try:
            # Find header section
            header = page.wait_for_selector("header", timeout=10000)
            
            # Check verification status
            try:
                verified_badge = page.locator("header span[aria-label*='Verified']").count()
                profile_data["verified"] = verified_badge > 0
            except:
                pass
            
            # Enhanced bio extraction with multiple approaches
            # Approach 1: Try to find bio div directly
            try:
                bio_div = page.wait_for_selector(
                    "div.-vDIg, div.QGPIr, div.xqs5bz0",
                    timeout=5000
                )
                if bio_div:
                    profile_data["bio"] = bio_div.text_content().strip()
                    print(f"Bio extracted (approach 1): {profile_data['bio'][:30]}...")
            except:
                print("Bio approach 1 failed, trying alternative methods...")
            
            # Approach 2: Check if bio is still empty, try span-based approach
            if not profile_data["bio"]:
                try:
                    # First try h1 followed by span which often contains bio
                    bio_spans = page.locator("section h1+span").all()
                    if bio_spans:
                        bio_text = ""
                        for span in bio_spans:
                            bio_text += span.text_content() + "\n"
                        profile_data["bio"] = bio_text.strip()
                        print(f"Bio extracted (approach 2a): {profile_data['bio'][:30]}...")
                except:
                    pass
            
            # Approach 3: Look for paragraphs or specific classes
            if not profile_data["bio"]:
                try:
                    bio_elements = page.locator("div._aa_c, div.xnz67gz, div.-vDIg").all()
                    if bio_elements:
                        for element in bio_elements:
                            text = element.text_content().strip()
                            if len(text) > 10:  # Likely a bio if it has some content
                                profile_data["bio"] = text
                                print(f"Bio extracted (approach 3): {profile_data['bio'][:30]}...")
                                break
                except:
                    pass
            
            # Extract name and website
            try:
                # Try to find name with improved selectors
                name_element = page.locator("section h2, header h2, h2._aacl").first
                if name_element:
                    profile_data["real_name"] = name_element.text_content().strip()
                    print(f"Name extracted: {profile_data['real_name']}")
                
                # Try to find website with improved selectors
                website_elements = page.locator("a[rel*='me'], a[rel*='nofollow']").all()
                if not website_elements:
                    website_elements = page.locator("a:not([href*='instagram.com']):not([href*='/explore/'])").all()
                
                for element in website_elements:
                    href = element.get_attribute("href")
                    if href and not ("instagram.com" in href or "/explore/" in href or "/followers/" in href or "/following/" in href):
                        profile_data["website"] = href
                        print(f"Website extracted: {profile_data['website']}")
                        break
            except Exception as e:
                print(f"Error extracting name/website details: {str(e)}")
            
            # Extract counts (posts, followers, following)
            try:
                # Try multiple selectors for counts
                counts = page.locator("header ul li, section ul li, li._aa_5").all()
                
                if len(counts) >= 3:
                    try:
                        posts_text = counts[0].text_content()
                        profile_data["post_count"] = int(posts_text.split()[0].replace(',', ''))
                    except:
                        pass
                    
                    try:
                        followers_text = counts[1].text_content()
                        followers_count = followers_text.split()[0]
                        if 'k' in followers_count.lower():
                            profile_data["followers"] = int(float(followers_count.replace('k', '')) * 1000)
                        elif 'm' in followers_count.lower():
                            profile_data["followers"] = int(float(followers_count.replace('m', '')) * 1000000)
                        else:
                            profile_data["followers"] = int(followers_count.replace(',', ''))
                    except:
                        pass
                    
                    try:
                        following_text = counts[2].text_content()
                        following_count = following_text.split()[0]
                        if 'k' in following_count.lower():
                            profile_data["following"] = int(float(following_count.replace('k', '')) * 1000)
                        elif 'm' in following_count.lower():
                            profile_data["following"] = int(float(following_count.replace('m', '')) * 1000000)
                        else:
                            profile_data["following"] = int(following_count.replace(',', ''))
                    except:
                        pass
            except Exception as e:
                print(f"Error extracting counts: {str(e)}")
            
            # Now extract the latest 6 image posts
            try:
                print(f"Extracting posts for {username}...")
                
                # Scroll down slightly to load posts
                page.evaluate("window.scrollBy(0, 300);")
                time.sleep(2)
                
                # Try different selectors for finding posts
                post_elements = None
                
                # Attempt 1: Find posts using article and a elements
                try:
                    post_elements = page.wait_for_selector_all("article a[href*='/p/']", timeout=10000)
                    print(f"Found {len(post_elements)} posts using selector 1")
                except:
                    print("Selector 1 failed, trying selector 2...")
                
                # Attempt 2: Try alternative selector
                if not post_elements or len(post_elements) == 0:
                    try:
                        post_elements = page.locator("article a[href*='/p/']").all()
                        print(f"Found {len(post_elements)} posts using selector 2")
                    except:
                        print("Selector 2 failed, trying selector 3...")
                
                # Attempt 3: Try finding the grid directly
                if not post_elements or len(post_elements) == 0:
                    try:
                        # Find the grid of posts
                        grid = page.wait_for_selector("div._aagv, div[style*='grid']", timeout=10000)
                        post_elements = grid.query_selector_all("a[href*='/p/']")
                        print(f"Found {len(post_elements)} posts using selector 3")
                    except:
                        print("Selector 3 failed, trying selector 4...")
                
                # Attempt 4: Try a more generic approach
                if not post_elements or len(post_elements) == 0:
                    try:
                        # Just find all links that could be posts
                        post_elements = page.locator("a[href*='/p/']").all()
                        print(f"Found {len(post_elements)} posts using selector 4")
                    except:
                        print("Selector 4 failed.")
                
                # Scroll down to load more posts if needed
                if not post_elements or len(post_elements) < 10:
                    print("Not enough posts found, scrolling to load more...")
                    for _ in range(3):  # Scroll a few times
                        page.evaluate("window.scrollBy(0, 1000);")
                        time.sleep(2)
                    
                    # Try to find posts again
                    try:
                        post_elements = page.locator("a[href*='/p/']").all()
                        print(f"After scrolling, found {len(post_elements)} posts")
                    except:
                        print("Failed to find more posts after scrolling.")
                
                # Debug information
                if not post_elements or len(post_elements) == 0:
                    print(f"Could not find any posts for {username}. Saving page source for debugging.")
                    with open(f"{output_dir}/{username}_page_source.html", "w", encoding="utf-8") as f:
                        f.write(page.content())
                
                # Extract up to 6 latest image posts
                image_posts_count = 0
                processed_urls = set()  # Keep track of posts we've already processed
                
                if post_elements and len(post_elements) > 0:
                    print(f"Found {len(post_elements)} total posts. Will extract up to 6 image posts...")
                    
                    # We need to process more posts to find 6 images
                    for post_idx, post in enumerate(post_elements[:100]):  # Try up to 100 posts to find 6 images
                        if image_posts_count >= 6:
                            break
                        
                        try:
                            post_url = post.get_attribute("href")
                            
                            # Skip if we've already processed this URL
                            if post_url in processed_urls:
                                continue
                            
                            processed_urls.add(post_url)
                            
                            # Skip reels
                            if "/reel/" in post_url:
                                print(f"Skipping reel: {post_url}")
                                continue
                            
                            print(f"Opening post {post_idx+1}: {post_url}")
                            
                            # Fix for relative URLs - ensure we have the full Instagram URL
                            if post_url.startswith('/'):
                                post_url = f"https://www.instagram.com{post_url}"
                            
                            # Open post in a new page
                            post_page = page.context.new_page()
                            post_page.goto(post_url)
                            time.sleep(3)
                            
                            # Check if it's really an image post (not a video, carousel with videos, or reel)
                            is_video = False
                            
                            # Check for video elements
                            video_elements = post_page.locator("video").count()
                            if video_elements > 0:
                                print(f"Post contains video, skipping: {post_url}")
                                is_video = True
                            
                            # Also check for video indicators in the UI
                            if not is_video:
                                video_indicators = post_page.locator("span[aria-label*='Video'], span[class*='video']").count()
                                if video_indicators > 0:
                                    print(f"Post has video indicators, skipping: {post_url}")
                                    is_video = True
                            
                            # Check for special video player UI elements
                            if not is_video:
                                video_ui_elements = post_page.locator("div._abpo, div[aria-label*='Play'], div[aria-label*='Pause']").count()
                                if video_ui_elements > 0:
                                    print(f"Post has video player UI elements, skipping: {post_url}")
                                    is_video = True
                            
                            if is_video:
                                # Close the post page and skip this post
                                post_page.close()
                                continue
                            
                            # Create post data
                            post_data = {
                                "url": post_url,
                                "thumbnail_url": "",
                                "timestamp": "",
                                "caption": "",
                                "likes": 0,
                                "comments": [],  # Changed to store actual comments
                                "comments_count": 0
                            }
                            
                            # Get high-resolution image
                            try:
                                # Try multiple selectors for finding the image
                                img_element = None
                                selectors = [
                                    "article div[role='button'] img",
                                    "article img:not([alt*='profile picture'])",
                                    "div[role='dialog'] article img",
                                    "div[role='dialog'] img:not([alt*='profile picture'])"
                                ]
                                
                                for selector in selectors:
                                    try:
                                        img_element = post_page.locator(selector).first
                                        if img_element:
                                            break
                                    except:
                                        continue
                                
                                if img_element:
                                    post_data["thumbnail_url"] = img_element.get_attribute("src")
                                    print(f"Found high-res image: {post_data['thumbnail_url'][:50]}...")
                                else:
                                    print("Could not find image in post")
                                    post_page.close()
                                    continue
                            except Exception as e:
                                print(f"Error getting high-res image: {str(e)}")
                                post_page.close()
                                continue
                            
                            # Get post caption
                            try:
                                caption_elements = post_page.locator("div[role='menuitem'] span, h1+span, div[role='dialog'] span:has-text(' ')").all()
                                if caption_elements:
                                    post_data["caption"] = caption_elements[0].text_content()
                                    print(f"Caption: {post_data['caption'][:30]}...")
                            except Exception as e:
                                print(f"Error getting caption: {str(e)}")
                            
                            # Get post time
                            try:
                                time_element = post_page.locator("time").first
                                if time_element:
                                    post_data["timestamp"] = time_element.get_attribute("datetime")
                                    print(f"Timestamp: {post_data['timestamp']}")
                            except Exception as e:
                                print(f"Error getting timestamp: {str(e)}")
                            
                            # Get likes and comments
                            try:
                                stats_elements = post_page.locator("section span").all()
                                for element in stats_elements:
                                    text = element.text_content().lower()
                                    if "like" in text:
                                        likes_text = text.split(" ")[0]
                                        try:
                                            post_data["likes"] = parse_count(likes_text)
                                            print(f"Likes: {post_data['likes']}")
                                        except:
                                            pass
                            except Exception as e:
                                print(f"Error getting likes/comments: {str(e)}")
                            
                            # Download the image
                            if post_data["thumbnail_url"]:
                                try:
                                    response = requests.get(post_data["thumbnail_url"], stream=True)
                                    if response.status_code == 200:
                                        post_id = post_url.split("/p/")[1].split("/")[0]
                                        image_filename = f"{username}_{post_id}.jpg"
                                        image_path = os.path.join(image_dir, image_filename)
                                        
                                        with open(image_path, 'wb') as img_file:
                                            for chunk in response.iter_content(1024):
                                                img_file.write(chunk)
                                        
                                        post_data["local_path"] = image_path
                                        print(f"Downloaded image post for {username} (post {image_posts_count+1}/6)")
                                        
                                        # Add post to profile data
                                        profile_data["posts"].append(post_data)
                                        image_posts_count += 1
                                    else:
                                        print(f"Failed to download image for post: {post_url}, status: {response.status_code}")
                                except Exception as e:
                                    print(f"Error downloading post image: {str(e)}")
                            
                            # Close the post page
                            post_page.close()
                            time.sleep(1)
                            
                        except Exception as e:
                            print(f"Error processing post: {str(e)}")
                            # Make sure to close any additional tabs
                            try:
                                post_page.close()
                            except:
                                pass
                    
                    print(f"Downloaded {image_posts_count} image posts for {username}")
                else:
                    print(f"No posts found for {username}")

            except Exception as e:
                print(f"Error extracting posts for {username}: {str(e)}")
        
        except Exception as e:
            print(f"Error extracting data for {username}: {str(e)}")
        
        return profile_data
    
    except Exception as e:
        print(f"Error scraping profile {username}: {str(e)}")
        return profile_data

# Helper function to parse counts like "1k", "2.5M", etc.
def parse_count(count_text):
    try:
        count_text = count_text.replace(',', '')
        if 'k' in count_text.lower():
            return int(float(count_text.lower().replace('k', '')) * 1000)
        elif 'm' in count_text.lower():
            return int(float(count_text.lower().replace('m', '')) * 1000000)
        else:
            return int(count_text)
    except:
        return 0

if __name__ == "__main__":
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
                        exit(1)
                    
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
                                exit(1)
                            
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
                            exit(1)
                
                # Now scrape profiles
                profile_data_list = []
                not_found_profiles = []
                
                for user in users:
                    print(f"\n=== Starting to scrape profile for: {user} ===")
                    profile_data = scrape_profile(page, user)
                    if profile_data:
                        # Transform the profile_data to the requested format
                        formatted_posts = []
                        for idx, post in enumerate(profile_data["posts"]):
                            formatted_post = {
                                "index": idx + 1,
                                "src": post.get("thumbnail_url", ""),
                                "alt": f"Photo by {profile_data['username']} on {post.get('timestamp', '').split('T')[0] if post.get('timestamp') else ''}.",
                                "likes": str(post.get("likes", 0)),
                                "caption": post.get("caption", ""),
                                "comments": post.get("comments", [])
                            }
                            formatted_posts.append(formatted_post)
                        
                        # Create the formatted data structure with all profile info
                        formatted_data = {
                            "username": profile_data.get("username", ""),
                            "real_name": profile_data.get("real_name", ""),
                            "bio": profile_data.get("bio", ""),
                            "website": profile_data.get("website", ""),
                            "private": profile_data.get("private", False),
                            "verified": profile_data.get("verified", False),
                            "post_count": profile_data.get("post_count", 0),
                            "followers": profile_data.get("followers", 0),
                            "following": profile_data.get("following", 0),
                            "posts": formatted_posts
                        }
                        
                        # Save the JSON data for this profile
                        json_filename = f"{output_dir}/profile_data_{user}_{timestamp}.json"
                        with open(json_filename, 'w', encoding='utf-8') as json_file:
                            json.dump(formatted_data, json_file, indent=2)
                        print(f"✓ Profile data for {user} saved to {json_filename}")
                        
                        profile_data_list.append(formatted_data)
                    else:
                        not_found_profiles.append(user)
                        print(f"⚠️ Could not scrape profile for: {user}")
                
                # Print summary
                print("\n=== Scraping Summary ===")
                print(f"Successfully scraped {len(profile_data_list)} profiles")
                if not_found_profiles:
                    print(f"Failed to scrape {len(not_found_profiles)} profiles: {', '.join(not_found_profiles)}")
            
            else:
                print("Invalid choice. Please run the script again and enter 1 or 2.")
            
            # Close the browser
            browser.close()
            print("Browser closed.")

    except Exception as e:
        print(f"Error during execution: {str(e)}")