import os
import json
import requests
import uuid
import time
from datetime import datetime
from insta_scraper_playwright import login_to_instagram, scrape_profile
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

class LocalWorkflowController:
    def __init__(self):
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        self.api_base_url = os.getenv('API_BASE_URL', 'http://65.0.99.113:8000')
        self.output_dir = "output"
        self.instagram_username = os.getenv('INSTAGRAM_USERNAME')
        self.instagram_password = os.getenv('INSTAGRAM_PASSWORD')
        
        os.makedirs(self.output_dir, exist_ok=True)

    def create_queue_directory(self, username):
        """Create organized directory structure for queue processing"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        queue_id = str(uuid.uuid4())[:8]
        queue_name = f"{username}_{timestamp}_{queue_id}"
        
        # Main queue directory
        queue_dir = os.path.join(self.output_dir, queue_name)
        
        # Subdirectories
        product_dir = os.path.join(queue_dir, "product")
        product_images_dir = os.path.join(product_dir, "images")
        competitor_dir = os.path.join(queue_dir, "competitor")
        competitor_images_dir = os.path.join(competitor_dir, "images")
        analysis_dir = os.path.join(queue_dir, "analysis")
        
        # Create all directories
        for dir_path in [queue_dir, product_dir, product_images_dir, 
                        competitor_dir, competitor_images_dir, analysis_dir]:
            os.makedirs(dir_path, exist_ok=True)
        
        return queue_id, queue_dir, product_dir, competitor_dir, analysis_dir, product_images_dir, competitor_images_dir

    def call_llm_analysis(self, profile_data, image_posts):
        """Call unified API for LLM analysis"""
        try:
            response = requests.post(
                f"{self.api_base_url}/api/llm/analyze-sector",
                json={
                    "profile_data": profile_data,
                    "posts_data": image_posts  # Changed from "image_posts" to "posts_data"
                },
                timeout=60
            )
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ LLM API error: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ LLM API request failed: {str(e)}")
            return None

    def call_search_competitors(self, sector, keywords, exclude_username=None):
        """Call unified API for competitor search"""
        try:
            response = requests.post(
                f"{self.api_base_url}/api/search-competitors",  # Fixed: removed '/search/'
                json={
                    "sector": sector,
                    "keywords": keywords,
                    "exclude_username": exclude_username or ""
                },
                timeout=60
            )
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Search API error: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Search API request failed: {str(e)}")
            return None

    def call_description_analysis(self, original_profile, competitor_profiles):
        """Call unified API for description analysis"""
        try:
            response = requests.post(
                f"{self.api_base_url}/api/description/analyze-descriptions",  # Changed from '/analyze' to '/analyze-descriptions'
                json={
                    "product_profile": original_profile,  # Changed from 'original_profile' to 'product_profile'
                    "competitor_profiles": competitor_profiles
                },
                timeout=60
            )
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Description API error: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Description API request failed: {str(e)}")
            return None

    def upload_to_s3(self, queue_id, bucket_name, local_directory):
        """Upload files to S3 via cloud service (no local AWS credentials needed)"""
        try:
            # Collect all files to upload
            files_to_upload = []
            for root, dirs, files in os.walk(local_directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Preserve directory structure in filename
                    relative_path = os.path.relpath(file_path, local_directory)
                    files_to_upload.append((relative_path, file_path))
            
            # Prepare multipart form data
            files = []
            for relative_path, full_path in files_to_upload:
                files.append(('files', (relative_path, open(full_path, 'rb'), 'application/octet-stream')))
            
            # Send files to cloud service
            response = requests.post(
                f"{self.api_base_url}/api/s3/upload-files",
                files=files,
                data={
                    'queue_id': queue_id,
                    'bucket_name': bucket_name
                }
            )
            
            # Close file handles
            for _, (_, file_handle, _) in files:
                file_handle.close()
            
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"Upload failed: {response.status_code}: {response.text}")
                
        except Exception as e:
            raise Exception(f"S3 upload error: {str(e)}")
            
    def scrape_instagram_profile(self, username, image_dir_override=None):
        """Local Instagram scraping using Playwright with proper image directory"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                storage_state="playwright_profile/state.json" if os.path.exists("playwright_profile/state.json") else None
            )
            page = context.new_page()
            
            try:
                # Check if login is needed
                if not os.path.exists("playwright_profile/state.json"):
                    print("🔐 Logging into Instagram...")
                    login_success = login_to_instagram(page, self.instagram_username, self.instagram_password)
                    if login_success:
                        print("✅ Login successful")
                    else:
                        print("❌ Login failed")
                        return None
                
                # Scrape profile with custom image directory
                print(f"📊 Scraping profile: @{username}")
                profile_data = scrape_profile(page, username, image_dir_override=image_dir_override)
                
                return profile_data
                
            except Exception as e:
                print(f"❌ Scraping error: {str(e)}")
                return None
            finally:
                browser.close()

    def run_local_workflow(self, username, upload_to_s3=True, s3_bucket="smm-analysis-bucket"):
        """Main workflow with description analysis and S3 upload"""
        print(f"🚀 Starting analysis for @{username}")
        
        # Create organized directory structure
        queue_id, queue_dir, product_dir, competitor_dir, analysis_dir, product_images_dir, competitor_images_dir = self.create_queue_directory(username)
        print(f"📁 Created queue directory: {queue_dir}")
        
        # Step A: Local scraping - PRODUCT (with proper image directory)
        print("📊 Step A: Scraping original profile (LOCAL)")
        original_profile = self.scrape_instagram_profile(username, image_dir_override=product_images_dir)
        if not original_profile:
            return None
        
        # Save product profile
        product_file = os.path.join(product_dir, f"{username}_profile.json")
        with open(product_file, 'w', encoding='utf-8') as f:
            json.dump(original_profile, f, indent=2, ensure_ascii=False)
        
        # Step B: Cloud LLM Analysis
        print("🤖 Step B: LLM sector analysis (CLOUD)")
        llm_result = self.call_llm_analysis(original_profile, original_profile.get('image_posts', []))
        if not llm_result:
            return None
        
        # Step C: Cloud Google Search
        print("🔍 Step C: Google search for competitors (CLOUD)")
        search_results = self.call_search_competitors(
            llm_result['sector'], 
            llm_result['keywords'], 
            username  # Pass username as exclude parameter
        )
        if not search_results:
            return None
        
        # Step D: Local scraping - COMPETITORS (with proper image directory)
        print("📊 Step D: Scraping competitor profiles (LOCAL)")
        scraped_competitors = []
        
        for competitor_username in search_results['instagram_usernames'][:1]:  # Only scrape 1
            print(f"📊 Scraping competitor: @{competitor_username}")
            competitor_profile = self.scrape_instagram_profile(competitor_username, image_dir_override=competitor_images_dir)
            
            if competitor_profile:
                # Save competitor profile
                competitor_file = os.path.join(competitor_dir, f"{competitor_username}_profile.json")
                with open(competitor_file, 'w', encoding='utf-8') as f:
                    json.dump(competitor_profile, f, indent=2, ensure_ascii=False)
                
                scraped_competitors.append(competitor_profile)
                print(f"✅ Competitor @{competitor_username} scraped successfully")
            else:
                print(f"❌ Failed to scrape competitor @{competitor_username}")
        
        # Step E: Cloud Description Analysis
        print("📝 Step E: Description analysis (CLOUD)")
        description_result = self.call_description_analysis(original_profile, scraped_competitors)  # Add scraped_competitors
        
        # Save description analysis
        if description_result:
            description_file = os.path.join(analysis_dir, "description_analysis.json")
            with open(description_file, 'w', encoding='utf-8') as f:
                json.dump(description_result, f, indent=2, ensure_ascii=False)
        
        # Step F: Consolidate results
        print("📋 Step F: Consolidating analysis results")
        final_result = {
            "username": username,
            "queue_id": queue_id,
            "timestamp": datetime.now().isoformat(),
            "sector_analysis": llm_result,  # Fixed variable name
            "search_results": search_results,
            "competitors": [comp for comp in scraped_competitors],  # Fixed iteration
            "description_analysis": description_result,
            "status": "completed"
        }
        
        # Save final analysis
        final_file = os.path.join(analysis_dir, "final_analysis.json")
        with open(final_file, 'w', encoding='utf-8') as f:
            json.dump(final_result, f, indent=2, ensure_ascii=False)  # Fixed variable name
        
        # Create summary
        summary = {
            "username": username,
            "queue_id": queue_id,
            "sector": llm_result.get('sector', 'Unknown'),
            "competitors_found": len(scraped_competitors),  # Fixed variable name
            "analysis_complete": True,
            "timestamp": datetime.now().isoformat()
        }
        
        summary_file = os.path.join(queue_dir, "summary.json")
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Analysis complete!")
        print(f"📁 Queue ID: {queue_id}")
        print(f"📂 All data saved to: {queue_dir}")
        print(f"📋 Summary: {summary_file}")
        
        # Step G: S3 Upload and Worker Trigger
        if upload_to_s3:
            print(f"\n☁️  Step G: Uploading to S3 and triggering worker analysis...")
            upload_result = self.upload_to_s3(queue_id, s3_bucket, queue_dir)
            if upload_result:
                print(f"✅ S3 upload successful - Worker analysis triggered!")
                print(f"🔄 Worker will process: {upload_result.get('message', 'Processing...')}")
            else:
                print(f"❌ S3 upload failed - Worker analysis not triggered")
        
        return final_result  # Fixed variable name

    def login_and_save_session(self):
        """Option 1: Login to Instagram and save session"""
        print("🔐 Opening Instagram for login...")
        print("📌 Instructions:")
        print("   1. Complete your login on Instagram")
        print("   2. Once logged in, close the browser window")
        print("   3. Your session will be saved automatically")
        
        session_saved = False
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            
            # Create profile directory if it doesn't exist
            os.makedirs("playwright_profile", exist_ok=True)
            
            context = browser.new_context()
            page = context.new_page()
            
            # Set up event listener for page close
            def on_page_close():
                nonlocal session_saved
                if not session_saved:
                    try:
                        context.storage_state(path="playwright_profile/state.json")
                        session_saved = True
                        print("\n✅ Login session saved successfully!")
                        print("📁 Session saved to: playwright_profile/state.json")
                    except Exception as e:
                        print(f"\n⚠️  Error saving session: {str(e)}")
            
            page.on("close", on_page_close)
            
            try:
                # Navigate to Instagram login page directly
                print("🌐 Loading Instagram login page...")
                page.goto("https://www.instagram.com/accounts/login/")
                
                # Wait for login form to load
                try:
                    page.wait_for_selector("input[name='username']", timeout=15000)
                    print("✅ Login page loaded successfully!")
                except:
                    print("⚠️  Direct login page failed, trying main page...")
                    page.goto("https://www.instagram.com/")
                    time.sleep(3)
                
                print("\n⏳ Waiting for you to login and close the browser...")
                print("💡 After successful login, simply close the browser window")
                
                # Wait for browser to be closed by user
                try:
                    while True:
                        try:
                            # Try to get current page - this will fail if browser is closed
                            if len(context.pages) == 0:
                                break
                            # Check if the main page is still accessible
                            page.title()  # This will throw if page is closed
                        except Exception:
                            # Browser/page has been closed
                            break
                        time.sleep(0.5)
                except KeyboardInterrupt:
                    print("\n🛑 Process interrupted by user")
                
                # Final attempt to save session if not already saved
                if not session_saved:
                    try:
                        context.storage_state(path="playwright_profile/state.json")
                        print("✅ Login session saved successfully!")
                        print("📁 Session saved to: playwright_profile/state.json")
                    except Exception as e:
                        print(f"⚠️  Final session save attempt failed: {str(e)}")
                        
            except Exception as e:
                print(f"❌ Error during login process: {str(e)}")
            finally:
                try:
                    if not session_saved:
                        # Last ditch effort to save session
                        context.storage_state(path="playwright_profile/state.json")
                        print("✅ Session saved in cleanup!")
                except:
                    pass
                
                try:
                    browser.close()
                except:
                    pass
    
    def check_saved_session(self):
        """Check if saved login session exists"""
        return os.path.exists("playwright_profile/state.json")
    
    def scrape_with_saved_session(self, username):
        """Option 2: Use existing saved login session to start scraping"""
        if not self.check_saved_session():
            print("❌ No saved login session found!")
            print("💡 Please use Option 1 first to login and save your session.")
            return None
        
        print(f"🚀 Starting scraping for @{username} using saved session...")
        return self.run_local_workflow(username)

if __name__ == "__main__":
    controller = LocalWorkflowController()
    
    print("🎯 Instagram Scraper - Choose an option:")
    print("\n1️⃣  Login to Instagram (saves session for future use)")
    print("2️⃣  Start scraping with saved session")
    
    # Check if saved session exists
    if controller.check_saved_session():
        print("✅ Saved login session found!")
    else:
        print("⚠️  No saved session found - you'll need to login first")
    
    choice = input("\nEnter your choice (1 or 2): ").strip()
    
    if choice == "1":
        controller.login_and_save_session()
        print("\n✨ Login complete! You can now use Option 2 to start scraping.")
        
    elif choice == "2":
        if not controller.check_saved_session():
            print("❌ No saved session found! Please use Option 1 first.")
        else:
            username = input("Enter Instagram username to analyze: ").strip()
            if username:
                controller.scrape_with_saved_session(username)
            else:
                print("❌ Please provide a username")
    
    else:
        print("❌ Invalid choice. Please enter 1 or 2.")