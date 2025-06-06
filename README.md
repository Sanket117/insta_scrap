# Instagram Profile Analyzer

A Python tool that analyzes Instagram profiles and identifies competitors using AI.

## What it does

- Scrapes Instagram profile data (followers, posts, bio)
- Uses Claude AI to find competitors in the same business sector
- Analyzes competitor profiles automatically
- Generates business descriptions

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
playwright install
```

2. Create `.env` file:
```bash
ANTHROPIC_API_KEY="your_api_key_here"
```

## Usage

Run the script:
```bash
python main.py
```

Choose from:
- Login to Instagram (saves session for reuse)
- Analyze Instagram Profile (main analysis function)

## How it works

1. Login to Instagram and save session
2. Enter target username to analyze
3. Tool scrapes profile data and saves to JSON
4. AI identifies 3+ competitors based on business sector
5. Tool scrapes competitor profiles
6. Generates business descriptions for all profiles

## Output

Data is saved in organized folders:
- `output/product_data/` - Target profile info
- `output/competitor_data/` - Competitor lists
- `output/competitor_profiles/` - Competitor profile data
- `output/descriptions/` - Business descriptions

## Core Functions in main.py

1. **prod_profile_scrape(username, login_choice=None, bypass_login_choice=False)**
   - Main function that handles Instagram profile scraping
   - Manages browser session and login process
   - Scrapes target profile data and saves it to JSON
   - Identifies top competitors and saves competitor data

2. **get_top_competitor(product_company_name)**
   - Uses Claude AI to identify top competitors for a given company
   - Analyzes Instagram profile data to determine business sector
   - Returns a list of competitors with their Instagram handles and metrics
   - Implements fallback system for reliable competitors by business sector

3. **comp_profile_scrape(profile_name)**
   - Scrapes the profile of top competitors based on competitor JSON data
   - Tries multiple competitors in order of follower count
   - Implements fallback to reliable competitors if scraping fails
   - Returns profile data of the successfully scraped competitor

4. **scrape_competitor_profile(username, profile_name)**
   - Helper function that handles the browser automation for competitor profile scraping
   - Uses saved login session to access Instagram
   - Saves competitor profile data including posts to JSON
   - Creates dedicated directories for competitor images

5. **generate_company_descriptions(profile_name)**
   - Uses Claude AI to generate concise business descriptions
   - Creates descriptions for both the target company and its top competitor
   - Analyzes Instagram profile data including bio and follower count
   - Saves descriptions as JSON files in the output directory

6. **Main execution flow** (if __name__ == "__main__")
   - Provides a command-line interface with two options:
     1. Login to Instagram (saves session for future use)
     2. Analyze an Instagram profile (performs full analysis workflow)
