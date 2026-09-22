import logging
import os
import time
from typing import List, Optional

from job_sourcing.connectors.base import IJobConnector, JobOfferDTO, get_random_user_agent
from job_sourcing.models import JobSource
from job_sourcing.connectors.linkedin.parser import LinkedInGuestParser

logger = logging.getLogger(__name__)

class LinkedInConnectorError(Exception):
    """Base exception for LinkedIn connector errors."""
    pass

class LinkedInConnectorTimeoutError(LinkedInConnectorError):
    """Raised when LinkedIn connector times out."""
    pass

class LinkedInConnectorNetworkError(LinkedInConnectorError):
    """Raised when LinkedIn connector encounters network errors."""
    pass

class LinkedInConnectorHTTPError(LinkedInConnectorError):
    """Raised when LinkedIn connector encounters HTTP errors."""
    def __init__(self, status_code: int, message: str = ""):
        self.status_code = status_code
        self.message = message
        super().__init__(f"HTTP {status_code}: {message}")

class LinkedInConnectorAccessDeniedError(LinkedInConnectorError):
    """Raised when LinkedIn connector is denied access (rate limit, blocked, etc.)."""
    pass

class LinkedInConnectorMalformedResponseError(LinkedInConnectorError):
    """Raised when LinkedIn connector receives malformed responses."""
    pass

class LinkedInConnector(IJobConnector):
    """
    LinkedIn connector using public guest API endpoints.
    
    Uses LinkedIn's undocumented public guest API that requires no authentication.
    Note: This uses public data and may be subject to LinkedIn's terms of service.
    
    Configuration (environment variables):
    - LINKEDIN_ENABLED: Enable/disable LinkedIn connector (default: true)
    - LINKEDIN_MOCK_MODE: Use mock data for testing (default: false)
    - LINKEDIN_MAX_JOBS: Maximum number of jobs to fetch per collection (default: 25)
    - LINKEDIN_PAGE_SIZE: Number of jobs per pagination page (default: 25)
    - LINKEDIN_REQUEST_TIMEOUT: HTTP request timeout in seconds (default: 10)
    - LINKEDIN_REQUEST_DELAY: Delay between requests in seconds (default: 1.0)
    
    No paid API key or authentication required.
    """
    
    def __init__(self):
        self._api_available: Optional[bool] = None
    
    @property
    def LINKEDIN_ENABLED(self) -> bool:
        """Enable/disable LinkedIn connector. Default: true."""
        return os.getenv("LINKEDIN_ENABLED", "true").lower() == "true"
    
    @property
    def LINKEDIN_MOCK_MODE(self) -> bool:
        """Use mock data for testing. Default: false (must be explicitly enabled)."""
        return os.getenv("LINKEDIN_MOCK_MODE", "false").lower() == "true"
    
    @property
    def LINKEDIN_MAX_JOBS(self) -> int:
        """Maximum number of jobs to fetch per collection. Default: 25."""
        return int(os.getenv("LINKEDIN_MAX_JOBS", "25"))
    
    @property
    def LINKEDIN_PAGE_SIZE(self) -> int:
        """Number of jobs per pagination page. Default: 25."""
        return int(os.getenv("LINKEDIN_PAGE_SIZE", "25"))
    
    @property
    def LINKEDIN_REQUEST_TIMEOUT(self) -> int:
        """HTTP request timeout in seconds. Default: 10."""
        return int(os.getenv("LINKEDIN_REQUEST_TIMEOUT", "10"))
    
    @property
    def LINKEDIN_REQUEST_DELAY(self) -> float:
        """Delay between requests in seconds. Default: 1.0."""
        return float(os.getenv("LINKEDIN_REQUEST_DELAY", "1.0"))
    
    def is_available(self) -> bool:
        """
        Check if LinkedIn connector is available.
        
        Returns False if explicitly disabled via configuration.
        Otherwise returns True (public endpoint is accessible).
        """
        if not self.LINKEDIN_ENABLED:
            logger.info("LinkedIn connector is disabled via LINKEDIN_ENABLED")
            return False
        
        if self._api_available is None:
            # Lightweight availability check - just verify we can reach the endpoint
            try:
                import requests
                url = f"{LinkedInGuestParser.SEARCH_URL}?keywords=test&start=0"
                headers = {"User-Agent": get_random_user_agent()}
                response = requests.head(url, headers=headers, timeout=5)
                self._api_available = response.status_code == 200
                if not self._api_available:
                    logger.warning(f"LinkedIn guest API returned HTTP {response.status_code}")
            except Exception as e:
                logger.warning(f"LinkedIn availability check failed: {e}")
                self._api_available = False
        
        return self._api_available if self._api_available is not None else True

    def fetch_offers(self, source: JobSource, keywords: str) -> List[JobOfferDTO]:
        """
        Fetch job offers from LinkedIn.
        
        Args:
            source: JobSource configuration
            keywords: Search keywords
            
        Returns:
            List of JobOfferDTO objects. Empty list if disabled or no jobs found.
            
        Raises:
            LinkedInConnectorError: If connector is configured but fails to fetch
        """
        logger.info(f"LinkedIn connector fetching offers for keywords: {keywords}")
        
        # Check if connector is available
        if not self.is_available():
            logger.error("LinkedIn connector is not available")
            return []
        
        # Use mock mode if explicitly enabled
        if self.LINKEDIN_MOCK_MODE:
            logger.info("LinkedIn connector running in MOCK mode")
            return self._fetch_via_mock(keywords)
        
        # Use real API (may raise LinkedInConnectorError)
        try:
            return self._fetch_via_api(source, keywords)
        except LinkedInConnectorError as e:
            logger.error(f"LinkedIn connector error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in LinkedIn connector: {e}")
            raise LinkedInConnectorError(f"Unexpected error: {e}")

    def _fetch_via_api(self, source: JobSource, keywords: str) -> List[JobOfferDTO]:
        """
        Fetch offers using LinkedIn's public guest API with pagination.
        
        Args:
            source: JobSource configuration
            keywords: Search keywords
            
        Returns:
            List of JobOfferDTO objects
            
        Raises:
            LinkedInConnectorTimeoutError: When request times out
            LinkedInConnectorNetworkError: When network error occurs
            LinkedInConnectorHTTPError: When HTTP error occurs
            LinkedInConnectorAccessDeniedError: When access is denied/rate limited
            LinkedInConnectorMalformedResponseError: When response is malformed
        """
        import requests
        
        page_size = self.LINKEDIN_PAGE_SIZE
        max_jobs = self.LINKEDIN_MAX_JOBS
        timeout = self.LINKEDIN_REQUEST_TIMEOUT
        delay = self.LINKEDIN_REQUEST_DELAY
        
        all_jobs_data = []
        start = 0
        
        try:
            logger.info(f"Fetching LinkedIn jobs with pagination (page_size={page_size}, max_jobs={max_jobs})")
            logger.info(f"Keywords: {keywords}")
            
            while len(all_jobs_data) < max_jobs:
                url = f"{LinkedInGuestParser.SEARCH_URL}?keywords={keywords}&start={start}"
                headers = {"User-Agent": get_random_user_agent()}
                
                logger.info(f"Fetching page: start={start}, current_total={len(all_jobs_data)}")
                response = requests.get(url, headers=headers, timeout=timeout)
                
                if response.status_code != 200:
                    if response.status_code in (403, 429):
                        raise LinkedInConnectorAccessDeniedError(
                            response.status_code, 
                            f"Access denied or rate limited by LinkedIn on page start={start}"
                        )
                    else:
                        raise LinkedInConnectorHTTPError(
                            response.status_code,
                            f"LinkedIn API returned HTTP {response.status_code} on page start={start}"
                        )
                
                # Parse search response
                try:
                    jobs_data = LinkedInGuestParser.parse_search_response(response.text)
                except Exception as e:
                    raise LinkedInConnectorMalformedResponseError(f"Failed to parse LinkedIn response: {e}")
                
                if not jobs_data:
                    logger.info(f"No jobs found on page start={start}, stopping pagination")
                    break
                
                logger.info(f"Found {len(jobs_data)} jobs on page start={start}")
                
                # Add to collection
                all_jobs_data.extend(jobs_data)
                
                # Check if we've reached max jobs
                if len(all_jobs_data) >= max_jobs:
                    all_jobs_data = all_jobs_data[:max_jobs]
                    logger.info(f"Reached max_jobs limit ({max_jobs})")
                    break
                
                # Prepare for next page
                start += page_size
                
                # Add delay before next request
                if len(all_jobs_data) < max_jobs:
                    time.sleep(delay)
            
            logger.info(f"Pagination complete: {len(all_jobs_data)} total jobs fetched")
            
            # Fast mapping for job DTOs (limit detail requests to top 3 max to ensure fast response)
            job_dtos = []
            for i, job_data in enumerate(all_jobs_data[:10]):
                try:
                    # Fetch details for top 3 jobs only to avoid blocking real-time search
                    if i < 3:
                        details = LinkedInGuestParser.fetch_job_details(job_data['job_id'])
                        if details and details.get('description'):
                            job_data['description'] = details['description']
                            if details.get('company'):
                                job_data['company'] = details['company']
                            if details.get('location'):
                                job_data['location'] = details['location']
                    
                    dto = LinkedInGuestParser.map_to_job_offer_dto(job_data)
                    job_dtos.append(dto)
                except Exception as e:
                    logger.warning(f"Failed to process job {job_data.get('job_id')}: {e}")
                    dto = LinkedInGuestParser.map_to_job_offer_dto(job_data)
                    job_dtos.append(dto)
            
            logger.info(f"Successfully fetched {len(job_dtos)} LinkedIn job offers")
            return job_dtos
            
        except requests.exceptions.Timeout:
            logger.error("LinkedIn API request timed out")
            raise LinkedInConnectorTimeoutError("LinkedIn API request timed out")
        except requests.exceptions.RequestException as e:
            logger.error(f"LinkedIn API request failed: {e}")
            raise LinkedInConnectorNetworkError(f"LinkedIn API request failed: {e}")
        except LinkedInConnectorError:
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching LinkedIn jobs: {e}")
            raise LinkedInConnectorError(f"Unexpected error fetching LinkedIn jobs: {e}")

    def _fetch_via_playwright(self, source: JobSource, keywords: str) -> List[JobOfferDTO]:
        """Playwright strategy not implemented for public API approach."""
        logger.warning("Playwright strategy not used for LinkedIn public API")
        return []

    def _fetch_via_mock(self, keywords: str) -> List[JobOfferDTO]:
        """Mock data for testing only."""
        logger.warning("LinkedIn connector returning MOCK data (testing mode)")
        all_mocks = [
            JobOfferDTO(
                raw_title="Data Scientist (Tunis / Hybride)",
                raw_company="InstaDeep",
                raw_location="Tunis, Tunisie",
                raw_description="Nous recherchons un ingénieur ou chercheur en Data Science pour rejoindre notre bureau de Tunis. Vous collaborerez à la recherche de pointe en LLM et renforcement par apprentissage. Profil requis : Python, PyTorch, JAX, Git, solide niveau en mathématiques.",
                raw_url="https://www.linkedin.com/jobs/view/instadeep-data-scientist-tunis",
                raw_posted_date=None
            ),
            JobOfferDTO(
                raw_title="Développeur Python Backend FastAPI",
                raw_company="Cegid",
                raw_location="Tunis, Tunisie",
                raw_description="Cegid recrute un développeur Backend Python en CDI. Vous participerez au développement de nouvelles fonctionnalités pour notre plateforme SaaS. Compétences requises : Python 3+, FastAPI, PostgreSQL, Architecture Microservices.",
                raw_url="https://www.linkedin.com/jobs/view/cegid-python-backend-tunis",
                raw_posted_date=None
            ),
            JobOfferDTO(
                raw_title="Machine Learning Engineer (NLP / RAG)",
                raw_company="Société Générale",
                raw_location="Paris, France",
                raw_description="Rejoignez notre centre d'excellence IA pour concevoir des applications sémantiques internes. Analyse de contrats, assistant virtuel intelligent, et traitement de gros volumes de documents textuels. Compétences : Python, Hugging Face, LangChain, Elasticsearch.",
                raw_url="https://www.linkedin.com/jobs/view/sg-ml-engineer-paris",
                raw_posted_date=None
            ),
            JobOfferDTO(
                raw_title="Data Engineer Senior",
                raw_company="BlaBlaCar",
                raw_location="Paris, France",
                raw_description="En tant que Data Engineer Senior, vous rejoindrez l'équipe Core Data pour maintenir notre Datalake. Compétences requises : Python, Spark, Scala, GCP, BigQuery, Airflow, dbt.",
                raw_url="https://www.linkedin.com/jobs/view/blablacar-data-engineer-senior",
                raw_posted_date=None
            )
        ]
        
        filtered = [
            job for job in all_mocks
            if keywords.lower() in job.raw_title.lower() 
            or keywords.lower() in job.raw_description.lower()
        ]
        
        return filtered if filtered else all_mocks
