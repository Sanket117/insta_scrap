from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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
    'khushiyaanorg',
    # Add more users as needed
]

# Setup directories
output_dir = "E:/audit-ai-automation-main-insta-extension/profile_data"
os.makedirs(output_dir, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
image_dir = f"{output_dir}/profile_images_{timestamp}"
os.makedirs(image_dir, exist_ok=True)

# Setup Chrome driver
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-notifications")
chrome_options.add_argument("--disable-infobars")
chrome_options.add_argument("--mute-audio")

service = Service("E:/audit-ai-automation-main-insta-extension/chromedriver.exe")
driver = webdriver.Chrome(service=service, options=chrome_options)

# Function to handle login
def login_to_instagram():
    driver.get("https://www.instagram.com/")
    time.sleep(3)
    
    # Handle cookies popup if it appears
    try:
        cookie_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'Allow')]"))
        )
        cookie_button.click()
        print("### Cookies: Accept [x]")
        time.sleep(2)
    except:
        print("### Cookies window not found. Skipping to login..")
    
    # Enter username and password
    print("### Entering in Instagram Username and Password..")
    try:
        username_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='username']"))
        )
        password_field = driver.find_element(By.CSS_SELECTOR, "input[name='password']")
        
        username_field.send_keys(username)
        password_field.send_keys(password)
        
        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_button.click()
        time.sleep(5)
    except Exception as e:
        print(f"Error during login: {str(e)}")
        return False
    
    # Handle "Save Login Info" popup
    try:
        not_now_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Not Now')]"))
        )
        not_now_button.click()
        print("### Save Login Info: Not Now [x]")
        time.sleep(2)
    except:
        print("Save Login Info popup not found. Skipping..")
    
    # Handle "Notifications" popup
    try:
        not_now_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Not Now')]"))
        )
        not_now_button.click()
        print("### Notifications: Not Now [x]")
        time.sleep(2)
    except:
        print("Notifications popup not found. Skipping..")
    
    return True

# Function to scrape profile data
def scrape_profile(username):
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
        driver.get(f"https://www.instagram.com/{username}/")
        time.sleep(5)
        
        # Check if profile exists
        if "Page Not Found" in driver.title or "Sorry, this page isn't available." in driver.page_source:
            print(f"Profile not found: {username}")
            return None
        
        # Extract profile data using modern selectors
        try:
            # Find header section
            header = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//header"))
            )
            
            # Check verification status
            try:
                verified_badge = header.find_elements(By.XPATH, ".//span[contains(@aria-label, 'Verified')]")
                profile_data["verified"] = len(verified_badge) > 0
            except:
                pass
            
            # Extract name, bio, website
            try:
                sections = driver.find_elements(By.XPATH, "//section/div")
                for section in sections:
                    # Try to find name
                    try:
                        h2_elements = section.find_elements(By.XPATH, ".//h2")
                        if h2_elements:
                            profile_data["real_name"] = h2_elements[0].text
                    except:
                        pass
                    
                    # Try to find bio and website
                    try:
                        span_elements = section.find_elements(By.XPATH, ".//span")
                        if span_elements and len(span_elements) > 1:
                            bio_text = ""
                            for span in span_elements:
                                bio_text += span.text + "\n"
                            profile_data["bio"] = bio_text.strip()
                    except:
                        pass
                    
                    # Try to find website
                    try:
                        a_elements = section.find_elements(By.XPATH, ".//a[not(contains(@href, 'instagram.com'))]")
                        if a_elements:
                            profile_data["website"] = a_elements[0].get_attribute("href")
                    except:
                        pass
            except Exception as e:
                print(f"Error extracting profile details: {str(e)}")
            
            # Extract counts (posts, followers, following)
            try:
                counts = driver.find_elements(By.XPATH, "//header//ul/li")
                if len(counts) >= 3:
                    try:
                        posts_text = counts[0].text
                        profile_data["post_count"] = int(posts_text.split()[0].replace(',', ''))
                    except:
                        pass
                    
                    try:
                        followers_text = counts[1].text
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
                        following_text = counts[2].text
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
                driver.execute_script("window.scrollBy(0, 300);")
                time.sleep(2)
                
                # Try different selectors for finding posts
                post_elements = None
                
                # Attempt 1: Find posts using article and a elements
                try:
                    post_elements = WebDriverWait(driver, 10).until(
                        EC.presence_of_all_elements_located((By.XPATH, "//article//a[contains(@href, '/p/')]"))
                    )
                    print(f"Found {len(post_elements)} posts using selector 1")
                except:
                    print("Selector 1 failed, trying selector 2...")
                
                # Attempt 2: Try alternative selector
                if not post_elements or len(post_elements) == 0:
                    try:
                        post_elements = WebDriverWait(driver, 10).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "article a[href*='/p/']"))
                        )
                        print(f"Found {len(post_elements)} posts using selector 2")
                    except:
                        print("Selector 2 failed, trying selector 3...")
                
                # Attempt 3: Try finding the grid directly
                if not post_elements or len(post_elements) == 0:
                    try:
                        # Find the grid of posts
                        grid = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, "//div[contains(@class, '_aagv') or contains(@style, 'grid')]"))
                        )
                        post_elements = grid.find_elements(By.XPATH, ".//a[contains(@href, '/p/')]")
                        print(f"Found {len(post_elements)} posts using selector 3")
                    except:
                        print("Selector 3 failed, trying selector 4...")
                
                # Attempt 4: Try a more generic approach
                if not post_elements or len(post_elements) == 0:
                    try:
                        # Just find all links that could be posts
                        post_elements = driver.find_elements(By.XPATH, "//a[contains(@href, '/p/')]")
                        print(f"Found {len(post_elements)} posts using selector 4")
                    except:
                        print("Selector 4 failed.")
                
                # Scroll down to load more posts if needed
                if not post_elements or len(post_elements) < 10:
                    print("Not enough posts found, scrolling to load more...")
                    for _ in range(3):  # Scroll a few times
                        driver.execute_script("window.scrollBy(0, 1000);")
                        time.sleep(2)
                    
                    # Try to find posts again
                    try:
                        post_elements = driver.find_elements(By.XPATH, "//a[contains(@href, '/p/')]")
                        print(f"After scrolling, found {len(post_elements)} posts")
                    except:
                        print("Failed to find more posts after scrolling.")
                
                # Debug information
                if not post_elements or len(post_elements) == 0:
                    print(f"Could not find any posts for {username}. Saving page source for debugging.")
                    with open(f"{output_dir}/{username}_page_source.html", "w", encoding="utf-8") as f:
                        f.write(driver.page_source)
                
                # Extract up to 6 latest image posts
                image_posts_count = 0
                processed_urls = set()  # Keep track of posts we've already processed
                
                if post_elements and len(post_elements) > 0:
                    print(f"Found {len(post_elements)} total posts. Will extract up to 6 image posts...")
                    
                    # We need to process more posts to find 6 images
                    for post_idx, post in enumerate(post_elements[:50]):  # Try up to 20 posts to find 6 images
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
                            
                            # Open the post to get more details
                            driver.execute_script("window.open(arguments[0]);", post_url)
                            time.sleep(2)
                            driver.switch_to.window(driver.window_handles[1])
                            time.sleep(3)
                            
                            # Check if it's really an image post (not a video, carousel with videos, or reel)
                            is_video = False
                            
                            # Check for video elements
                            video_elements = driver.find_elements(By.TAG_NAME, "video")
                            if len(video_elements) > 0:
                                print(f"Post contains video, skipping: {post_url}")
                                is_video = True
                            
                            # Also check for video indicators in the UI
                            if not is_video:
                                video_indicators = driver.find_elements(By.XPATH, "//span[contains(@aria-label, 'Video') or contains(@class, 'video')]")
                                if len(video_indicators) > 0:
                                    print(f"Post has video indicators, skipping: {post_url}")
                                    is_video = True
                            
                            # Check for special video player UI elements
                            if not is_video:
                                video_ui_elements = driver.find_elements(By.XPATH, "//div[contains(@class, '_abpo') or contains(@aria-label, 'Play') or contains(@aria-label, 'Pause')]")
                                if len(video_ui_elements) > 0:
                                    print(f"Post has video player UI elements, skipping: {post_url}")
                                    is_video = True
                            
                            if is_video:
                                # Close the post tab and skip this post
                                driver.close()
                                driver.switch_to.window(driver.window_handles[0])
                                continue
                            
                            # Create post data
                            post_data = {
                                "url": post_url,
                                "thumbnail_url": "",
                                "timestamp": "",
                                "caption": "",
                                "likes": 0,
                                "comments": 0
                            }
                            
                            # Get high-resolution image
                            try:
                                # Try multiple selectors for finding the image
                                img_element = None
                                selectors = [
                                    "//article//div[contains(@role, 'button')]//img",
                                    "//article//img[not(ancestor::header)]",
                                    "article div[role='button'] img",
                                    "//div[@role='dialog']//img[not(ancestor::header)]",
                                    "//div[contains(@role, 'dialog')]//article//img"
                                ]
                                
                                for selector in selectors:
                                    try:
                                        if selector.startswith("//"):
                                            img_element = driver.find_element(By.XPATH, selector)
                                        else:
                                            img_element = driver.find_element(By.CSS_SELECTOR, selector)
                                        if img_element:
                                            break
                                    except:
                                        continue
                                
                                if img_element:
                                    post_data["thumbnail_url"] = img_element.get_attribute("src")
                                    print(f"Found high-res image: {post_data['thumbnail_url'][:50]}...")
                                else:
                                    print("Could not find image in post")
                                    driver.close()
                                    driver.switch_to.window(driver.window_handles[0])
                                    continue
                            except Exception as e:
                                print(f"Error getting high-res image: {str(e)}")
                                driver.close()
                                driver.switch_to.window(driver.window_handles[0])
                                continue
                            
                            # Get post caption
                            try:
                                caption_elements = driver.find_elements(By.XPATH, "//div[contains(@role, 'menuitem')]/span") or \
                                                       driver.find_elements(By.XPATH, "//h1/following-sibling::span") or \
                                                       driver.find_elements(By.XPATH, "//div[contains(@role, 'dialog')]//span[contains(text(), ' ')]")
                                if caption_elements:
                                    post_data["caption"] = caption_elements[0].text
                                    print(f"Caption: {post_data['caption'][:30]}...")
                            except Exception as e:
                                print(f"Error getting caption: {str(e)}")
                            
                            # Get post time
                            try:
                                time_elements = driver.find_elements(By.TAG_NAME, "time")
                                if time_elements:
                                    post_data["timestamp"] = time_elements[0].get_attribute("datetime")
                                    print(f"Timestamp: {post_data['timestamp']}")
                            except Exception as e:
                                print(f"Error getting timestamp: {str(e)}")
                            
                            # Get likes and comments
                            try:
                                stats_elements = driver.find_elements(By.XPATH, "//section//span")
                                for element in stats_elements:
                                    text = element.text.lower()
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
                            
                            # Close the post tab
                            driver.close()
                            driver.switch_to.window(driver.window_handles[0])
                            time.sleep(1)
                            
                        except Exception as e:
                            print(f"Error processing post: {str(e)}")
                            # Make sure to close any additional tabs
                            if len(driver.window_handles) > 1:
                                driver.close()
                                driver.switch_to.window(driver.window_handles[0])
                    
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

# Main execution
try:
    # Login to Instagram
    if not login_to_instagram():
        print("Failed to login. Exiting.")
        driver.quit()
        exit(1)
    
    # Scrape profiles
    profile_data_list = []
    not_found_profiles = []
    
    for user in users:
        profile_data = scrape_profile(user)
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
                    "comments": []  # This would need additional scraping to populate comments
                }
                formatted_posts.append(formatted_post)
            
            # Create the formatted data structure
            formatted_data = {
                "posts": formatted_posts
            }
            
            profile_data_list.append(formatted_data)
        else:
            not_found_profiles.append(user)
    
    # Save the JSON data
    for i, formatted_data in enumerate(profile_data_list):
        user = users[i] if i < len(users) else f"profile_{i}"
        json_filename = f"{output_dir}/profile_data_{user}_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as json_file:
            json.dump(formatted_data, json_file, indent=1)
        print(f"Profile data saved to {json_filename}")
    
    # Print summary
    print("\nThe following Instagram Profiles could not be found:")
    print(not_found_profiles)
    print(f"All post images saved to {image_dir}")
    print(f"Number of profiles scraped: {len(profile_data_list)}")

except Exception as e:
    print(f"Error during execution: {str(e)}")

finally:
    # Close the browser
    driver.quit()
