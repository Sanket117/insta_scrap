## Setup

1. Clone this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Create a `.env` file with your Anthropic API key:
```bash    
ANTHROPIC_API_KEY="your_api_key_here"
```
## Usage

Run the main script:
```bash
python main.py
```

The tool offers two main options:
1. **Login to Instagram**: Set up a persistent login session
2. **Analyze Instagram Profile**: Scrape a profile and analyze competitors

### Workflow

1. **Login**: First, log in to Instagram manually or use a saved session
2. **Profile Analysis**: Enter a username to analyze
3. **Competitor Discovery**: The tool finds top competitors using AI
4. **Competitor Analysis**: Scrapes the profiles of identified competitors

### Data Output

All data is stored in organized directories:
- `output/product_data/`: Target profile information
- `output/competitor_data/`: Competitor lists
- `output/competitor_profiles/`: Detailed competitor profile data
- `output/competitor_profiles/profile_images/`: Images from competitor profiles

## Functions

- `prod_profile_scrape()`: Scrapes a target Instagram profile
- `get_top_competitor()`: Uses AI to identify competitors
- `comp_profile_scrape()`: Scrapes competitor profiles

## Notes

- The tool uses a headless browser (can be visible for debugging)
- Login sessions are saved for reuse
