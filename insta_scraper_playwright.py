from playwright.sync_api import sync_playwright
import json
import os
import time
import requests
from datetime import datetime
import urllib.parse
from dotenv import load_dotenv

# Setup directories
output_dir = "output/product_data"
os.makedirs(output_dir, exist_ok=True)

image_dir = f"{output_dir}/profile_images"
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

# Function to scrape profile data
def scrape_profile(page, username, image_dir_override=None):
    """
    Scrapes an Instagram profile
    
    Args:
        page: The Playwright page object
        username: Instagram username to scrape
        image_dir_override: Optional custom directory for saving images
    
    Returns:
        Dictionary with profile data or None if failed
    """
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
    
    # Use the specified image directory if provided, otherwise use the default
    current_image_dir = image_dir_override if image_dir_override else image_dir
    
    # Ensure the image directory exists
    os.makedirs(current_image_dir, exist_ok=True)
    
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
            
            # Enhanced bio extraction
            try:
                bio_div = page.wait_for_selector(
                    "div.-vDIg, div.QGPIr, div.xqs5bz0, div._aa_c",
                    timeout=5000
                )
                if bio_div:
                    profile_data["bio"] = bio_div.text_content().strip()
            except:
                # Try alternative bio selectors if the first approach fails
                try:
                    bio_spans = page.locator("header section > div > span, section h1 ~ span").all()
                    if bio_spans:
                        bio_text = ""
                        for span in bio_spans:
                            bio_text += span.text_content() + "\n"
                        profile_data["bio"] = bio_text.strip()
                except:
                    pass
            
            # Extract name and website
            try:
                name_element = page.locator("section h2, header h2, h2._aacl").first
                if name_element:
                    profile_data["real_name"] = name_element.text_content().strip()
                
                website_elements = page.locator("a[rel*='me'], a[rel*='nofollow']").all()
                if not website_elements:
                    website_elements = page.locator("a:not([href*='instagram.com']):not([href*='/explore/'])").all()
                
                for element in website_elements:
                    href = element.get_attribute("href")
                    if href and not ("instagram.com" in href or "/explore/" in href or "/followers/" in href or "/following/" in href):
                        profile_data["website"] = href
                        break
            except Exception as e:
                print(f"Error extracting name/website details: {str(e)}")
            
            # Extract counts (posts, followers, following)
            try:
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
            
            # Now extract exactly 6 image posts - this is the part we're improving
            try:
                print(f"Extracting exactly 6 image posts for {username}...")
                
                # Check if profile is private first
                private_indicators = page.locator("h2:has-text('This Account is Private')").count()
                if private_indicators > 0:
                    profile_data["private"] = True
                    print(f"Warning: {username} is a private account. May not be able to extract posts.")
                
                # Scroll down to load more posts - do this multiple times to ensure we have enough posts
                for scroll_attempt in range(5):
                    page.evaluate(f"window.scrollBy(0, {1000 * (scroll_attempt + 1)});")
                    time.sleep(2)
                
                # Find posts using various selectors
                post_elements = []
                selectors = [
                    "article a[href*='/p/']",
                    "div._aagv a[href*='/p/'], div[style*='grid'] a[href*='/p/']",
                    "a[href*='/p/']"
                ]
                
                for selector in selectors:
                    try:
                        found_posts = page.locator(selector).all()
                        if found_posts and len(found_posts) > 0:
                            post_elements = found_posts
                            print(f"Found {len(post_elements)} posts using selector: {selector}")
                            break
                    except:
                        continue
                
                # If we still don't have enough posts, try scrolling more aggressively
                if not post_elements or len(post_elements) < 12:  # Try to get more than we need for fallbacks
                    print("Not enough posts found, scrolling more aggressively...")
                    for _ in range(3):
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(3)
                    
                    # Try to find posts again with all selectors
                    for selector in selectors:
                        try:
                            found_posts = page.locator(selector).all()
                            if found_posts and len(found_posts) > 0:
                                post_elements = found_posts
                                print(f"After aggressive scrolling, found {len(post_elements)} posts")
                                break
                        except:
                            continue
                
                # If we still don't have enough posts, try a more targeted approach
                if not post_elements or len(post_elements) < 6:
                    print("Still not enough posts, trying alternative approach...")
                    # Try to force-load the page with a reload and wait longer
                    page.reload()
                    time.sleep(5)
                    
                    # Scroll down in smaller increments
                    for i in range(10):
                        page.evaluate(f"window.scrollBy(0, 300);")
                        time.sleep(1)
                    
                    # Try one last time with all selectors
                    for selector in selectors:
                        try:
                            found_posts = page.locator(selector).all()
                            if found_posts and len(found_posts) > 0:
                                post_elements = found_posts
                                print(f"Final attempt found {len(post_elements)} posts")
                                break
                        except:
                            continue
                
                # Process posts to get exactly 6 image posts
                image_posts_count = 0
                processed_urls = set()  # Keep track of posts we've already processed
                
                # If we have private account with no visible posts
                if profile_data["private"] and (not post_elements or len(post_elements) == 0):
                    print(f"WARNING: {username} is private with no visible posts. Creating placeholders.")
                    # Create 6 placeholder posts
                    for i in range(6):
                        placeholder_post = {
                            "url": f"https://www.instagram.com/{username}/",
                            "thumbnail_url": "",
                            "timestamp": datetime.now().isoformat(),
                            "caption": "Private account - no visible posts",
                            "likes": 0,
                            "comments": [],
                            "comments_count": 0,
                            "is_placeholder": True
                        }
                        profile_data["posts"].append(placeholder_post)
                        image_posts_count += 1
                    
                    print(f"Created {image_posts_count} placeholder posts for private account")
                elif not post_elements or len(post_elements) == 0:
                    print(f"WARNING: No posts found for {username}. Creating placeholders.")
                    # Create 6 placeholder posts for accounts with no posts
                    for i in range(6):
                        placeholder_post = {
                            "url": f"https://www.instagram.com/{username}/",
                            "thumbnail_url": "",
                            "timestamp": datetime.now().isoformat(),
                            "caption": "No posts available",
                            "likes": 0,
                            "comments": [],
                            "comments_count": 0,
                            "is_placeholder": True
                        }
                        profile_data["posts"].append(placeholder_post)
                        image_posts_count += 1
                    
                    print(f"Created {image_posts_count} placeholder posts for account with no posts")
                else:
                    # Process up to 30 posts to find 6 images - this gives us plenty of attempts
                    # in case some posts are videos or stories
                    print(f"Found {len(post_elements)} posts. Processing to find 6 image posts...")
                    
                    max_attempts = min(50, len(post_elements))  # Try up to 50 posts to find 6 images
                    for post_idx, post in enumerate(post_elements[:max_attempts]):
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
                                continue
                            
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
                                is_video = True
                            
                            # Also check for video indicators in the UI
                            if not is_video:
                                video_indicators = post_page.locator("span[aria-label*='Video'], span[class*='video']").count()
                                if video_indicators > 0:
                                    is_video = True
                            
                            # Check for special video player UI elements
                            if not is_video:
                                video_ui_elements = post_page.locator("div._abpo, div[aria-label*='Play'], div[aria-label*='Pause']").count()
                                if video_ui_elements > 0:
                                    is_video = True
                            
                            # If it's a video, try to get the thumbnail anyway if we're running low on posts
                            force_use_video = False
                            if is_video and (post_idx >= max_attempts - 12) and image_posts_count < 4:
                                print(f"Running low on posts, using video thumbnail as fallback for post #{image_posts_count+1}")
                                force_use_video = True
                            
                            if is_video and not force_use_video:
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
                                "comments": [],
                                "comments_count": 0
                            }
                            
                            # Get high-resolution image
                            try:
                                # Try multiple selectors for finding the image
                                selectors = [
                                    "article div[role='button'] img",
                                    "article img:not([alt*='profile picture'])",
                                    "div[role='dialog'] article img",
                                    "div[role='dialog'] img:not([alt*='profile picture'])",
                                    "img[alt*='Photo by']",  # Common alt text format
                                    "img[sizes*='px']",      # Images typically have sizes attribute
                                    "img[src*='instagram']"  # Any Instagram-hosted image
                                ]
                                
                                for selector in selectors:
                                    try:
                                        img_element = post_page.locator(selector).first
                                        if img_element:
                                            post_data["thumbnail_url"] = img_element.get_attribute("src")
                                            print(f"Found high-res image for post {image_posts_count+1}")
                                            break
                                    except:
                                        continue
                                
                                # If we couldn't find an image, try taking a screenshot as last resort
                                if not post_data["thumbnail_url"] and image_posts_count < 5:
                                    try:
                                        print(f"No image found, taking screenshot for post {image_posts_count+1}")
                                        screenshot_path = os.path.join(current_image_dir, f"{username}_post_{image_posts_count+1}_screenshot.jpg")
                                        post_page.screenshot(path=screenshot_path)
                                        post_data["thumbnail_url"] = f"file://{screenshot_path}"  # Local file URL
                                        post_data["is_screenshot"] = True
                                    except Exception as ss_error:
                                        print(f"Error taking screenshot: {str(ss_error)}")
                                
                                if not post_data["thumbnail_url"]:
                                    post_page.close()
                                    continue
                            except Exception as e:
                                print(f"Error getting high-res image: {str(e)}")
                                post_page.close()
                                continue
                            
                            # Get post caption
                            try:
                                caption_selectors = [
                                    "div.C7I1f, div._a9zr, div[role='menuitem'] span, div._a9zs",
                                    "h1+span, div[role='dialog'] span:has-text(' ')",
                                    "article div > span > div > span"
                                ]
                                
                                for selector in caption_selectors:
                                    caption_elements = post_page.locator(selector).all()
                                    if caption_elements and len(caption_elements) > 0:
                                        post_data["caption"] = caption_elements[0].text_content().strip()
                                        break
                                
                                # Extract hashtags from caption
                                if post_data["caption"]:
                                    # Continue with existing code by adding the rest of the function
                                    hashtags = []
                                    words = post_data["caption"].split()
                                    for word in words:
                                        if word.startswith("#"):
                                            hashtags.append(word)
                                    
                                    post_data["hashtags"] = hashtags
                            except Exception as e:
                                print(f"Error extracting caption: {str(e)}")
                            
                            # Get post timestamp
                            try:
                                time_selectors = [
                                    "time[datetime]",
                                    "div._aaqe, div._aaqf, div[class*='timestamp']"
                                ]
                                
                                for selector in time_selectors:
                                    time_elements = post_page.locator(selector).all()
                                    if time_elements and len(time_elements) > 0:
                                        timestamp = time_elements[0].get_attribute("datetime")
                                        if timestamp:
                                            post_data["timestamp"] = timestamp
                                            break
                                        
                                        timestamp_text = time_elements[0].text_content().strip()
                                        if timestamp_text:
                                            post_data["timestamp"] = timestamp_text
                                            break
                            except Exception as e:
                                print(f"Error extracting timestamp: {str(e)}")
                            
                            # Get post likes/views
                            try:
                                like_selectors = [
                                    "section:has(span[aria-label*='like']), div._aacl:has-text('likes'), div[role='dialog'] span:has-text('likes')",
                                    "span[class*='like'], span.zV_eT, span._aap9"
                                ]
                                
                                for selector in like_selectors:
                                    like_elements = post_page.locator(selector).all()
                                    if like_elements and len(like_elements) > 0:
                                        like_text = like_elements[0].text_content().strip()
                                        
                                        # Extract just the number from text like "123 likes"
                                        like_text = ''.join(filter(lambda x: x.isdigit() or x in 'km,.', like_text.lower()))
                                        post_data["likes"] = parse_count(like_text)
                                        break
                            except Exception as e:
                                print(f"Error extracting likes: {str(e)}")
                            
                            # Get comments count
                            try:
                                comment_selectors = [
                                    "div[role='dialog'] span:has-text('comments'), span:has-text('View all')",
                                    "ul > li:has-text('comments'), span[class*='comment'], span._acbn"
                                ]
                                
                                for selector in comment_selectors:
                                    comment_elements = post_page.locator(selector).all()
                                    if comment_elements and len(comment_elements) > 0:
                                        comment_text = comment_elements[0].text_content().strip()
                                        
                                        # Extract just the number from text like "View all 123 comments"
                                        if "comments" in comment_text.lower():
                                            comment_text = comment_text.lower().replace("comments", "").replace("view all", "").strip()
                                            post_data["comments_count"] = parse_count(comment_text)
                                            break
                            except Exception as e:
                                print(f"Error extracting comments count: {str(e)}")
                            
                            # Download the image if we have a URL
                            if post_data["thumbnail_url"]:
                                try:
                                    # Create a sanitized filename
                                    date_part = ""
                                    if post_data["timestamp"]:
                                        try:
                                            if "T" in post_data["timestamp"]:
                                                # ISO format: YYYY-MM-DDTHH:MM:SS
                                                dt = datetime.fromisoformat(post_data["timestamp"].replace("Z", "+00:00"))
                                                date_part = dt.strftime("%Y%m%d_%H%M%S")
                                            else:
                                                # Just use timestamp as is
                                                date_part = post_data["timestamp"].replace(" ", "_").replace(":", "").replace("/", "")
                                        except:
                                            date_part = f"post_{image_posts_count}"
                                    else:
                                        date_part = f"post_{image_posts_count}"
                                    
                                    # Generate filename
                                    img_filename = f"{username}_{date_part}.jpg"
                                    safe_filename = "".join([c for c in img_filename if c.isalpha() or c.isdigit() or c in "._- "]).strip()
                                    img_path = os.path.join(current_image_dir, safe_filename)
                                    
                                    # If this is not a screenshot we already saved
                                    if not post_data.get("is_screenshot", False):
                                        # Download the image
                                        response = requests.get(post_data["thumbnail_url"], headers={"User-Agent": "Mozilla/5.0"})
                                        if response.status_code == 200:
                                            with open(img_path, "wb") as f:
                                                f.write(response.content)
                                            
                                            # Update post data with local image path
                                            post_data["local_image_path"] = img_path
                                            print(f"Downloaded image for post {image_posts_count+1}")
                                    else:
                                        # Already saved as screenshot
                                        post_data["local_image_path"] = post_data["thumbnail_url"].replace("file://", "")
                                except Exception as e:
                                    print(f"Error downloading image: {str(e)}")
                            
                            # Add the post data to our list
                            profile_data["posts"].append(post_data)
                            image_posts_count += 1
                            
                            # Close the post page
                            post_page.close()
                            
                        except Exception as e:
                            print(f"Error processing post {post_idx}: {str(e)}")
                            try:
                                post_page.close()
                            except:
                                pass
                
                # If we still don't have enough posts, add placeholders to reach exactly 6
                while image_posts_count < 6:
                    print(f"Adding placeholder post #{image_posts_count+1} to reach 6 total posts")
                    placeholder_post = {
                        "url": f"https://www.instagram.com/{username}/",
                        "thumbnail_url": "",
                        "timestamp": datetime.now().isoformat(),
                        "caption": "",
                        "likes": 0,
                        "comments": [],
                        "comments_count": 0,
                        "is_placeholder": True
                    }
                    profile_data["posts"].append(placeholder_post)
                    image_posts_count += 1
                    
                    print(f"Created {image_posts_count} placeholder posts for account with no posts")
                else:
                    # Process up to 30 posts to find 6 images - this gives us plenty of attempts
                    # in case some posts are videos or stories
                    print(f"Found {len(post_elements)} posts. Processing to find 6 image posts...")
                    
                    max_attempts = min(50, len(post_elements))  # Try up to 50 posts to find 6 images
                    for post_idx, post in enumerate(post_elements[:max_attempts]):
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
                                continue
                            
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
                                is_video = True
                            
                            # Also check for video indicators in the UI
                            if not is_video:
                                video_indicators = post_page.locator("span[aria-label*='Video'], span[class*='video']").count()
                                if video_indicators > 0:
                                    is_video = True
                            
                            # Check for special video player UI elements
                            if not is_video:
                                video_ui_elements = post_page.locator("div._abpo, div[aria-label*='Play'], div[aria-label*='Pause']").count()
                                if video_ui_elements > 0:
                                    is_video = True
                            
                            # If it's a video, try to get the thumbnail anyway if we're running low on posts
                            force_use_video = False
                            if is_video and (post_idx >= max_attempts - 12) and image_posts_count < 4:
                                print(f"Running low on posts, using video thumbnail as fallback for post #{image_posts_count+1}")
                                force_use_video = True
                            
                            if is_video and not force_use_video:
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
                                "comments": [],
                                "comments_count": 0
                            }
                            
                            # Get high-resolution image
                            try:
                                # Try multiple selectors for finding the image
                                selectors = [
                                    "article div[role='button'] img",
                                    "article img:not([alt*='profile picture'])",
                                    "div[role='dialog'] article img",
                                    "div[role='dialog'] img:not([alt*='profile picture'])",
                                    "img[alt*='Photo by']",  # Common alt text format
                                    "img[sizes*='px']",      # Images typically have sizes attribute
                                    "img[src*='instagram']"  # Any Instagram-hosted image
                                ]
                                
                                for selector in selectors:
                                    try:
                                        img_element = post_page.locator(selector).first
                                        if img_element:
                                            post_data["thumbnail_url"] = img_element.get_attribute("src")
                                            print(f"Found high-res image for post {image_posts_count+1}")
                                            break
                                    except:
                                        continue
                                
                                # If we couldn't find an image, try taking a screenshot as last resort
                                if not post_data["thumbnail_url"] and image_posts_count < 5:
                                    try:
                                        print(f"No image found, taking screenshot for post {image_posts_count+1}")
                                        screenshot_path = os.path.join(current_image_dir, f"{username}_post_{image_posts_count+1}_screenshot.jpg")
                                        post_page.screenshot(path=screenshot_path)
                                        post_data["thumbnail_url"] = f"file://{screenshot_path}"  # Local file URL
                                        post_data["is_screenshot"] = True
                                    except Exception as ss_error:
                                        print(f"Error taking screenshot: {str(ss_error)}")
                                
                                if not post_data["thumbnail_url"]:
                                    post_page.close()
                                    continue
                            except Exception as e:
                                print(f"Error getting high-res image: {str(e)}")
                                post_page.close()
                                continue
                            
                            # Get post caption
                            try:
                                caption_selectors = [
                                    "div.C7I1f, div._a9zr, div[role='menuitem'] span, div._a9zs",
                                    "h1+span, div[role='dialog'] span:has-text(' ')",
                                    "article div > span > div > span"
                                ]
                                
                                for selector in caption_selectors:
                                    caption_elements = post_page.locator(selector).all()
                                    if caption_elements and len(caption_elements) > 0:
                                        post_data["caption"] = caption_elements[0].text_content().strip()
                                        break
                                
                                # Extract hashtags from caption
                                if post_data["caption"]:
                                    # Continue with existing code by adding the rest of the function
                                    hashtags = []
                                    words = post_data["caption"].split()
                                    for word in words:
                                        if word.startswith("#"):
                                            hashtags.append(word)
                                    
                                    post_data["hashtags"] = hashtags
                            except Exception as e:
                                print(f"Error extracting caption: {str(e)}")
                            
                            # Get post timestamp
                            try:
                                time_selectors = [
                                    "time[datetime]",
                                    "div._aaqe, div._aaqf, div[class*='timestamp']"
                                ]
                                
                                for selector in time_selectors:
                                    time_elements = post_page.locator(selector).all()
                                    if time_elements and len(time_elements) > 0:
                                        timestamp = time_elements[0].get_attribute("datetime")
                                        if timestamp:
                                            post_data["timestamp"] = timestamp
                                            break
                                        
                                        timestamp_text = time_elements[0].text_content().strip()
                                        if timestamp_text:
                                            post_data["timestamp"] = timestamp_text
                                            break
                            except Exception as e:
                                print(f"Error extracting timestamp: {str(e)}")
                            
                            # Get post likes/views
                            try:
                                like_selectors = [
                                    "section:has(span[aria-label*='like']), div._aacl:has-text('likes'), div[role='dialog'] span:has-text('likes')",
                                    "span[class*='like'], span.zV_eT, span._aap9"
                                ]
                                
                                for selector in like_selectors:
                                    like_elements = post_page.locator(selector).all()
                                    if like_elements and len(like_elements) > 0:
                                        like_text = like_elements[0].text_content().strip()
                                        
                                        # Extract just the number from text like "123 likes"
                                        like_text = ''.join(filter(lambda x: x.isdigit() or x in 'km,.', like_text.lower()))
                                        post_data["likes"] = parse_count(like_text)
                                        break
                            except Exception as e:
                                print(f"Error extracting likes: {str(e)}")
                            
                            # Get comments count
                            try:
                                comment_selectors = [
                                    "div[role='dialog'] span:has-text('comments'), span:has-text('View all')",
                                    "ul > li:has-text('comments'), span[class*='comment'], span._acbn"
                                ]
                                
                                for selector in comment_selectors:
                                    comment_elements = post_page.locator(selector).all()
                                    if comment_elements and len(comment_elements) > 0:
                                        comment_text = comment_elements[0].text_content().strip()
                                        
                                        # Extract just the number from text like "View all 123 comments"
                                        if "comments" in comment_text.lower():
                                            comment_text = comment_text.lower().replace("comments", "").replace("view all", "").strip()
                                            post_data["comments_count"] = parse_count(comment_text)
                                            break
                            except Exception as e:
                                print(f"Error extracting comments count: {str(e)}")
                            
                            # Download the image if we have a URL
                            if post_data["thumbnail_url"]:
                                try:
                                    # Create a sanitized filename
                                    date_part = ""
                                    if post_data["timestamp"]:
                                        try:
                                            if "T" in post_data["timestamp"]:
                                                # ISO format: YYYY-MM-DDTHH:MM:SS
                                                dt = datetime.fromisoformat(post_data["timestamp"].replace("Z", "+00:00"))
                                                date_part = dt.strftime("%Y%m%d_%H%M%S")
                                            else:
                                                # Just use timestamp as is
                                                date_part = post_data["timestamp"].replace(" ", "_").replace(":", "").replace("/", "")
                                        except:
                                            date_part = f"post_{image_posts_count}"
                                    else:
                                        date_part = f"post_{image_posts_count}"
                                    
                                    # Generate filename
                                    img_filename = f"{username}_{date_part}.jpg"
                                    safe_filename = "".join([c for c in img_filename if c.isalpha() or c.isdigit() or c in "._- "]).strip()
                                    img_path = os.path.join(current_image_dir, safe_filename)
                                    
                                    # Download the image
                                    response = requests.get(post_data["thumbnail_url"], headers={"User-Agent": "Mozilla/5.0"})
                                    if response.status_code == 200:
                                        with open(img_path, "wb") as f:
                                            f.write(response.content)
                                        
                                        # Update post data with local image path
                                        post_data["local_image_path"] = img_path
                                        print(f"Downloaded image for post {image_posts_count+1}")
                                except Exception as e:
                                    print(f"Error downloading image: {str(e)}")
                            
                            # Add the post data to our list
                            profile_data["posts"].append(post_data)
                            image_posts_count += 1
                            
                            # Close the post page
                            post_page.close()
                            
                        except Exception as e:
                            print(f"Error processing post {post_idx}: {str(e)}")
                            try:
                                post_page.close()
                            except:
                                pass
                
                print(f"Extracted {image_posts_count} image posts for {username}")
            except Exception as e:
                print(f"Error extracting posts: {str(e)}")
            
            # Check if profile is private
            try:
                private_indicators = page.locator("h2:has-text('This Account is Private')").count()
                if private_indicators > 0:
                    profile_data["private"] = True
            except:
                pass
            
        except Exception as e:
            print(f"Error extracting profile data: {str(e)}")
    
    except Exception as e:
        print(f"Error scraping profile {username}: {str(e)}")
        return None
    
    # Save profile data to JSON
    try:
        output_path = os.path.join(output_dir, f"{username}_profile.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(profile_data, f, indent=4, ensure_ascii=False)
        print(f"Saved profile data for {username} to {output_path}")
    except Exception as e:
        print(f"Error saving profile data: {str(e)}")
    
    return profile_data

# After the scrape_profile function, add this new function

def prod_profile_scrape(product_name, username):
    """
    Scrape the profile of a product's Instagram account with dedicated image storage.
    
    Args:
        product_name (str): Name of the product for folder organization
        username (str): Instagram username to scrape
    
    Returns:
        dict: Profile data of the scraped account
    """
    try:
        # Create a dedicated directory for product profile images
        product_image_dir = f"output/product_data/profile_images/{product_name}"
        os.makedirs(product_image_dir, exist_ok=True)
        
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
                
                # Scrape profile for the product username with custom image directory
                product_data = scrape_profile(page, username, image_dir_override=product_image_dir)
                
                # Save profile data with product name
                if product_data:
                    output_path = os.path.join(output_dir, f"{product_name}.json")
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(product_data, f, indent=4, ensure_ascii=False)
                    print(f"✅ Saved product profile data for {username} to {output_path}")
                else:
                    print(f"❌ Failed to scrape profile for {username}")
                
                # Close browser
                browser.close()
                
                return product_data
                
            except Exception as e:
                print(f"❌ Error scraping product profile: {str(e)}")
                browser.close()
                return None
                
    except Exception as e:
        print(f"❌ Error in prod_profile_scrape: {str(e)}")
        return None

def main():
    # List of usernames to scrape
    users = [
        # Add Instagram usernames to scrape
        # For example:
        # "instagram",
        # "nike",
        # "natgeo"
    ]
    
    # Get usernames from command line if provided
    import sys
    if len(sys.argv) > 1:
        users = sys.argv[1:]
    
    # If no users specified, prompt for input
    if not users:
        user_input = input("Enter Instagram usernames to scrape (separated by commas): ")
        users = [username.strip() for username in user_input.split(",") if username.strip()]
    
    if not users:
        print("No usernames provided. Exiting.")
        return
    
    print(f"Will scrape profiles for: {', '.join(users)}")
    
    # Run with Playwright
    with sync_playwright() as p:
        # Launch the browser
        browser = p.chromium.launch(headless=False)  # Set headless=True for production
        
        # Create a context with viewport and user agent
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        
        # Create a new page
        page = context.new_page()
        
        # Login to Instagram
        if not login_to_instagram(page):
            print("Failed to log in to Instagram. Exiting.")
            browser.close()
            return
        
        # Scrape each profile
        for username in users:
            print(f"\n--- Scraping profile for {username} ---")
            profile_data = scrape_profile(page, username)
            
            if profile_data:
                print(f"Successfully scraped profile for {username}")
                print(f"Followers: {profile_data['followers']}")
                print(f"Following: {profile_data['following']}")
                print(f"Posts: {profile_data['post_count']}")
                print(f"Verified: {'Yes' if profile_data['verified'] else 'No'}")
                print(f"Private: {'Yes' if profile_data['private'] else 'No'}")
                print(f"Extracted {len(profile_data['posts'])} posts")
            else:
                print(f"Failed to scrape profile for {username}")
            
            # Wait a bit before scraping the next profile to avoid rate limiting
            time.sleep(5)
        
        # Close the browser
        browser.close()

if __name__ == "__main__":
    main()