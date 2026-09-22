"""
LinkedIn Guest API Parser
Extracts job data from LinkedIn's public guest API endpoints.
"""
import re
import logging
import requests
from typing import List, Optional, Dict
from bs4 import BeautifulSoup
from job_sourcing.connectors.base import JobOfferDTO

logger = logging.getLogger(__name__)

class LinkedInGuestParser:
    """Parser for LinkedIn guest API responses."""
    
    # LinkedIn guest API endpoints
    SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    JOB_DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
    
    @staticmethod
    def parse_search_response(html: str) -> List[Dict]:
        """
        Parse the search API response to extract job listings.
        
        Returns list of job dictionaries with:
        - job_id: LinkedIn job ID
        - title: Job title
        - company: Company name
        - location: Location
        - url: LinkedIn job URL
        - posted_date_raw: Raw posted date string
        """
        soup = BeautifulSoup(html, 'html.parser')
        jobs = []
        
        # Find all job cards by data-entity-urn attribute
        job_cards = soup.find_all('div', attrs={'data-entity-urn': True})
        
        for card in job_cards:
            try:
                # Extract job ID from data-entity-urn
                entity_urn = card.get('data-entity-urn', '')
                if not entity_urn.startswith('urn:li:jobPosting:'):
                    continue
                
                job_id = entity_urn.replace('urn:li:jobPosting:', '')
                
                # Extract title
                title_elem = card.find('h3', class_='base-search-card__title')
                title = title_elem.get_text(strip=True) if title_elem else None
                
                # Extract company
                company_elem = card.find('h4', class_='base-search-card__subtitle')
                if company_elem:
                    company_link = company_elem.find('a')
                    company = company_link.get_text(strip=True) if company_link else company_elem.get_text(strip=True)
                else:
                    company = None
                
                # Extract location
                location_elem = card.find('span', class_='job-search-card__location')
                location = location_elem.get_text(strip=True) if location_elem else None
                
                # Extract URL
                link_elem = card.find('a', class_='base-card__full-link')
                url = link_elem.get('href') if link_elem else None
                
                # Extract posted date
                time_elem = card.find('time', class_='job-search-card__listdate')
                posted_date_raw = time_elem.get('datetime') if time_elem else None
                
                if title and url:
                    jobs.append({
                        'job_id': job_id,
                        'title': title,
                        'company': company,
                        'location': location,
                        'url': url,
                        'posted_date_raw': posted_date_raw
                    })
                    
            except Exception as e:
                logger.warning(f"Failed to parse job card: {e}")
                continue
        
        return jobs
    
    @staticmethod
    def parse_job_detail(html: str) -> Optional[Dict]:
        """
        Parse the job detail API response to extract full description.
        
        Returns dictionary with:
        - description: Full job description
        - company: Company name (may be more detailed)
        - location: Location (may be more detailed)
        - posted_date_raw: Raw posted date string
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract description from show-more-less-html section
        desc_section = soup.find('section', class_='show-more-less-html')
        if desc_section:
            desc_markup = desc_section.find('div', class_='show-more-less-html__markup')
            if desc_markup:
                description = desc_markup.get_text(separator=' ', strip=True)
            else:
                description = desc_section.get_text(separator=' ', strip=True)
        else:
            description = None
        
        # Extract company from topcard
        company_link = soup.find('a', class_='topcard__org-name-link')
        company = company_link.get_text(strip=True) if company_link else None
        
        # Extract location from topcard flavor
        location_elem = soup.find('span', class_='topcard__flavor--bullet')
        location = location_elem.get_text(strip=True) if location_elem else None
        
        # Extract posted date
        posted_elem = soup.find('span', class_='posted-time-ago__text')
        posted_date_raw = posted_elem.get_text(strip=True) if posted_elem else None
        
        return {
            'description': description,
            'company': company,
            'location': location,
            'posted_date_raw': posted_date_raw
        }
    
    @staticmethod
    def fetch_job_details(job_id: str) -> Optional[Dict]:
        """
        Fetch full job details for a specific job ID.
        
        Returns dictionary with description and other details.
        """
        from job_sourcing.connectors.base import get_random_user_agent
        
        url = LinkedInGuestParser.JOB_DETAIL_URL.format(job_id=job_id)
        headers = {'User-Agent': get_random_user_agent()}
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return LinkedInGuestParser.parse_job_detail(response.text)
            else:
                logger.warning(f"Failed to fetch job details for {job_id}: HTTP {response.status_code}")
                return None
        except Exception as e:
            logger.warning(f"Failed to fetch job details for {job_id}: {e}")
            return None
    
    @staticmethod
    def map_to_job_offer_dto(job_data: Dict) -> JobOfferDTO:
        """
        Map parsed job data to JobOfferDTO.
        """
        return JobOfferDTO(
            raw_title=job_data.get('title', ''),
            raw_company=job_data.get('company', ''),
            raw_location=job_data.get('location', ''),
            raw_description=job_data.get('description', ''),
            raw_url=job_data.get('url', ''),
            raw_posted_date=job_data.get('posted_date_raw')
        )
