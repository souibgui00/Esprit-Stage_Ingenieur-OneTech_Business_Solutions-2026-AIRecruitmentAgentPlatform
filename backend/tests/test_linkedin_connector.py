"""
Tests for LinkedIn Connector with real public API integration.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import requests
from job_sourcing.connectors.linkedin.connector import (
    LinkedInConnector,
    LinkedInConnectorError,
    LinkedInConnectorTimeoutError,
    LinkedInConnectorNetworkError,
    LinkedInConnectorHTTPError,
    LinkedInConnectorAccessDeniedError,
    LinkedInConnectorMalformedResponseError
)
from job_sourcing.connectors.base import JobOfferDTO
from job_sourcing.models import JobSource, SourceType


@pytest.fixture
def linkedin_connector():
    """Create a LinkedIn connector instance."""
    return LinkedInConnector()


@pytest.fixture
def job_source():
    """Create a mock JobSource for testing."""
    return JobSource(
        name="linkedin",
        type=SourceType.SCRAPER,
        base_url="https://linkedin.com",
        is_active=True
    )


class TestLinkedInConnectorConfiguration:
    """Test LinkedIn connector configuration."""
    
    def test_default_configuration(self, linkedin_connector):
        """Test default configuration values."""
        assert linkedin_connector.LINKEDIN_ENABLED is True
        assert linkedin_connector.LINKEDIN_MAX_JOBS == 25
        assert linkedin_connector.LINKEDIN_REQUEST_TIMEOUT == 10
        assert linkedin_connector.LINKEDIN_REQUEST_DELAY == 1.0
        assert linkedin_connector.LINKEDIN_MOCK_MODE is False


class TestLinkedInConnectorAvailability:
    """Test LinkedIn connector availability checks."""
    
    def test_is_available_when_enabled(self, linkedin_connector):
        """Test availability when enabled and endpoint is accessible."""
        with patch('requests.head') as mock_head:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_head.return_value = mock_response
            
            assert linkedin_connector.is_available() is True
    
    def test_is_available_when_disabled(self):
        """Test availability when disabled via config."""
        import os
        original_value = os.environ.get('LINKEDIN_ENABLED')
        try:
            os.environ['LINKEDIN_ENABLED'] = 'false'
            connector = LinkedInConnector()
            assert connector.is_available() is False
        finally:
            if original_value is None:
                os.environ.pop('LINKEDIN_ENABLED', None)
            else:
                os.environ['LINKEDIN_ENABLED'] = original_value
    
    def test_is_available_http_error(self, linkedin_connector):
        """Test availability when endpoint returns HTTP error."""
        with patch('requests.head') as mock_head:
            mock_response = Mock()
            mock_response.status_code = 403
            mock_head.return_value = mock_response
            
            assert linkedin_connector.is_available() is False
    
    def test_is_available_network_error(self, linkedin_connector):
        """Test availability when network error occurs."""
        with patch('requests.head') as mock_head:
            mock_head.side_effect = Exception("Network error")
            
            assert linkedin_connector.is_available() is False


class TestLinkedInConnectorFetchOffers:
    """Test LinkedIn connector offer fetching."""
    
    def test_fetch_offers_when_disabled(self, linkedin_connector, job_source):
        """Test fetch returns empty when connector is disabled."""
        import os
        original_value = os.environ.get('LINKEDIN_ENABLED')
        try:
            os.environ['LINKEDIN_ENABLED'] = 'false'
            connector = LinkedInConnector()
            offers = connector.fetch_offers(job_source, "python")
            assert offers == []
        finally:
            if original_value is None:
                os.environ.pop('LINKEDIN_ENABLED', None)
            else:
                os.environ['LINKEDIN_ENABLED'] = original_value
    
    def test_fetch_offers_mock_mode(self, linkedin_connector, job_source):
        """Test fetch returns mock data in mock mode."""
        import os
        original_value = os.environ.get('LINKEDIN_MOCK_MODE')
        try:
            os.environ['LINKEDIN_MOCK_MODE'] = 'true'
            connector = LinkedInConnector()
            offers = connector.fetch_offers(job_source, "python")
            assert len(offers) > 0
            assert all(isinstance(offer, JobOfferDTO) for offer in offers)
        finally:
            if original_value is None:
                os.environ.pop('LINKEDIN_MOCK_MODE', None)
            else:
                os.environ['LINKEDIN_MOCK_MODE'] = original_value
    
    @patch('requests.get')
    def test_fetch_offers_success(self, mock_get, linkedin_connector, job_source):
        """Test successful fetch of real LinkedIn jobs."""
        import os
        original_max = os.environ.get('LINKEDIN_MAX_JOBS')
        
        try:
            # Set max_jobs to 1 for this test to avoid pagination
            os.environ['LINKEDIN_MAX_JOBS'] = '1'
            connector = LinkedInConnector()
            
            # Mock search response
            search_html = """
            <li>
              <div class="base-card relative w-full hover:no-underline focus:no-underline base-card--link base-search-card base-search-card--link job-search-card" data-entity-urn="urn:li:jobPosting:3952275643">
                <a class="base-card__full-link absolute top-0 right-0 bottom-0 left-0 p-0 z-[2]" href="https://www.linkedin.com/jobs/view/python-developer-3952275643">
                  <span class="sr-only">Python Developer</span>
                </a>
                <div class="base-search-card__info">
                  <h3 class="base-search-card__title">Python Developer</h3>
                  <h4 class="base-search-card__subtitle">
                    <a class="hidden-nested-link" href="https://www.linkedin.com/company/test-company">Test Company</a>
                  </h4>
                  <div class="base-search-card__metadata">
                    <span class="job-search-card__location">New York, NY</span>
                  </div>
                  <time class="job-search-card__listdate" datetime="2026-08-04">1 week ago</time>
                </div>
              </div>
            </li>
            """
            
            # Mock job detail response
            detail_html = """
            <section class="show-more-less-html">
                <div class="show-more-less-html__markup">
                    Job description here with Python skills.
                </div>
            </section>
            <a class="topcard__org-name-link">Test Company</a>
            <span class="topcard__flavor--bullet">New York, NY</span>
            <span class="posted-time-ago__text">1 week ago</span>
            """
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = search_html
            mock_get.return_value = mock_response
            
            # Patch the delay to avoid sleep in tests
            with patch('time.sleep'):
                # Patch fetch_job_details to return detail HTML
                with patch('job_sourcing.connectors.linkedin.parser.LinkedInGuestParser.fetch_job_details') as mock_details:
                    mock_details.return_value = {
                        'description': 'Job description here with Python skills.',
                        'company': 'Test Company',
                        'location': 'New York, NY',
                        'posted_date_raw': '1 week ago'
                    }
                    
                    offers = connector.fetch_offers(job_source, "python")
                    
                    assert len(offers) == 1
                    assert offers[0].raw_title == "Python Developer"
                    assert offers[0].raw_company == "Test Company"
                    assert offers[0].raw_location == "New York, NY"
                    assert offers[0].raw_description == "Job description here with Python skills."
        finally:
            if original_max:
                os.environ['LINKEDIN_MAX_JOBS'] = original_max
            else:
                os.environ.pop('LINKEDIN_MAX_JOBS', None)
    
    @patch('requests.get')
    def test_fetch_offers_http_error(self, mock_get, linkedin_connector, job_source):
        """Test fetch raises LinkedInConnectorHTTPError on generic HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 500  # Use 500 for generic HTTP error
        mock_get.return_value = mock_response
        
        with pytest.raises(LinkedInConnectorHTTPError):
            linkedin_connector.fetch_offers(job_source, "python")
    
    @patch('requests.get')
    def test_fetch_offers_timeout(self, mock_get, linkedin_connector, job_source):
        """Test fetch raises LinkedInConnectorTimeoutError on timeout."""
        mock_get.side_effect = requests.exceptions.Timeout()
        
        with pytest.raises(LinkedInConnectorTimeoutError):
            linkedin_connector.fetch_offers(job_source, "python")
    
    @patch('requests.get')
    def test_fetch_offers_network_error(self, mock_get, linkedin_connector, job_source):
        """Test fetch raises LinkedInConnectorNetworkError on network error."""
        mock_get.side_effect = requests.exceptions.RequestException("Network error")
        
        with pytest.raises(LinkedInConnectorNetworkError):
            linkedin_connector.fetch_offers(job_source, "python")
    
    @patch('requests.get')
    def test_fetch_offers_empty_response(self, mock_get, linkedin_connector, job_source):
        """Test fetch returns empty when no jobs found."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<div>No jobs here</div>"
        mock_get.return_value = mock_response
        
        offers = linkedin_connector.fetch_offers(job_source, "python")
        assert offers == []
    
    @patch('requests.get')
    def test_fetch_offers_max_jobs_limit(self, mock_get, linkedin_connector, job_source):
        """Test fetch respects max jobs limit."""
        # Create response with multiple jobs
        jobs_html = ""
        for i in range(30):
            jobs_html += f"""
            <li>
              <div class="base-card relative w-full hover:no-underline focus:no-underline base-card--link base-search-card base-search-card--link job-search-card" data-entity-urn="urn:li:jobPosting:39522756{i}">
                <a class="base-card__full-link absolute top-0 right-0 bottom-0 left-0 p-0 z-[2]" href="https://www.linkedin.com/jobs/view/job-{i}">
                  <span class="sr-only">Job {i}</span>
                </a>
                <div class="base-search-card__info">
                  <h3 class="base-search-card__title">Job {i}</h3>
                  <h4 class="base-search-card__subtitle">
                    <a class="hidden-nested-link" href="https://www.linkedin.com/company/test">Test Company</a>
                  </h4>
                  <div class="base-search-card__metadata">
                    <span class="job-search-card__location">Location</span>
                  </div>
                  <time class="job-search-card__listdate" datetime="2026-08-04">1 week ago</time>
                </div>
              </div>
            </li>
            """
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = jobs_html
        mock_get.return_value = mock_response
        
        with patch('time.sleep'):
            with patch('job_sourcing.connectors.linkedin.parser.LinkedInGuestParser.fetch_job_details') as mock_details:
                mock_details.return_value = {
                    'description': 'Description',
                    'company': 'Test Company',
                    'location': 'Location',
                    'posted_date_raw': '1 week ago'
                }
                
                offers = linkedin_connector.fetch_offers(job_source, "python")
                
                # Should be limited to LINKEDIN_MAX_JOBS (default 25)
                assert len(offers) == 25


class TestLinkedInConnectorErrorSemantics:
    """Test LinkedIn connector error semantics."""
    
    @patch('requests.get')
    def test_fetch_offers_timeout_raises_error(self, mock_get, linkedin_connector, job_source):
        """Test that timeout raises LinkedInConnectorTimeoutError."""
        mock_get.side_effect = requests.exceptions.Timeout()
        
        with pytest.raises(LinkedInConnectorTimeoutError):
            linkedin_connector.fetch_offers(job_source, "test")
    
    @patch('requests.get')
    def test_fetch_offers_network_error_raises_error(self, mock_get, linkedin_connector, job_source):
        """Test that network error raises LinkedInConnectorNetworkError."""
        mock_get.side_effect = requests.exceptions.ConnectionError()
        
        with pytest.raises(LinkedInConnectorNetworkError):
            linkedin_connector.fetch_offers(job_source, "test")
    
    @patch('requests.get')
    def test_fetch_offers_http_error_raises_error(self, mock_get, linkedin_connector, job_source):
        """Test that HTTP error raises LinkedInConnectorHTTPError."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        with pytest.raises(LinkedInConnectorHTTPError) as exc_info:
            linkedin_connector.fetch_offers(job_source, "test")
        
        assert exc_info.value.status_code == 500
    
    @patch('requests.get')
    def test_fetch_offers_access_denied_raises_error(self, mock_get, linkedin_connector, job_source):
        """Test that 403/429 raises LinkedInConnectorAccessDeniedError."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response
        
        with pytest.raises(LinkedInConnectorAccessDeniedError):
            linkedin_connector.fetch_offers(job_source, "test")
    
    @patch('requests.get')
    def test_fetch_offers_malformed_response_raises_error(self, mock_get, linkedin_connector, job_source):
        """Test that malformed response raises LinkedInConnectorMalformedResponseError."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "invalid html"
        mock_get.return_value = mock_response
        
        with patch('job_sourcing.connectors.linkedin.parser.LinkedInGuestParser.parse_search_response') as mock_parse:
            mock_parse.side_effect = Exception("Parse error")
            
            with pytest.raises(LinkedInConnectorMalformedResponseError):
                linkedin_connector.fetch_offers(job_source, "test")
    
    @patch('requests.get')
    def test_fetch_offers_empty_response_is_success(self, mock_get, linkedin_connector, job_source):
        """Test that empty response is treated as success (no jobs found)."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<div>No jobs</div>"
        mock_get.return_value = mock_response
        
        with patch('job_sourcing.connectors.linkedin.parser.LinkedInGuestParser.parse_search_response') as mock_parse:
            mock_parse.return_value = []
            
            offers = linkedin_connector.fetch_offers(job_source, "test")
            
            # Empty response should return empty list, not raise error
            assert offers == []


class TestLinkedInConnectorMockMode:
    """Test LinkedIn connector mock mode."""
    
    def test_mock_mode_returns_filtered_jobs(self, linkedin_connector, job_source):
        """Test mock mode filters jobs by keyword."""
        import os
        original_value = os.environ.get('LINKEDIN_MOCK_MODE')
        try:
            os.environ['LINKEDIN_MOCK_MODE'] = 'true'
            connector = LinkedInConnector()
            offers = connector.fetch_offers(job_source, "python")
            
            # Should return jobs matching "python"
            assert len(offers) > 0
            assert all("python" in offer.raw_title.lower() or "python" in offer.raw_description.lower() 
                      for offer in offers)
        finally:
            if original_value is None:
                os.environ.pop('LINKEDIN_MOCK_MODE', None)
            else:
                os.environ['LINKEDIN_MOCK_MODE'] = original_value
    
    def test_mock_mode_returns_all_if_no_match(self, linkedin_connector, job_source):
        """Test mock mode returns all jobs if no keyword match."""
        import os
        original_value = os.environ.get('LINKEDIN_MOCK_MODE')
        try:
            os.environ['LINKEDIN_MOCK_MODE'] = 'true'
            connector = LinkedInConnector()
            offers = connector.fetch_offers(job_source, "nonexistentkeyword")
            
            # Should return all mock jobs when no match
            assert len(offers) == 4
        finally:
            if original_value is None:
                os.environ.pop('LINKEDIN_MOCK_MODE', None)
            else:
                os.environ['LINKEDIN_MOCK_MODE'] = original_value


class TestLinkedInConnectorPagination:
    """Test LinkedIn connector pagination."""
    
    @patch('requests.get')
    def test_pagination_multiple_pages(self, mock_get, linkedin_connector, job_source):
        """Test pagination across multiple pages."""
        import os
        original_max = os.environ.get('LINKEDIN_MAX_JOBS')
        original_page = os.environ.get('LINKEDIN_PAGE_SIZE')
        
        try:
            os.environ['LINKEDIN_MAX_JOBS'] = '75'
            os.environ['LINKEDIN_PAGE_SIZE'] = '25'
            connector = LinkedInConnector()
            
            # First page returns 25 jobs
            page1_html = self._generate_job_html(25, start_id=1)
            page2_html = self._generate_job_html(25, start_id=26)
            page3_html = self._generate_job_html(25, start_id=51)
            
            mock_response1 = Mock()
            mock_response1.status_code = 200
            mock_response1.text = page1_html
            
            mock_response2 = Mock()
            mock_response2.status_code = 200
            mock_response2.text = page2_html
            
            mock_response3 = Mock()
            mock_response3.status_code = 200
            mock_response3.text = page3_html
            
            mock_get.side_effect = [mock_response1, mock_response2, mock_response3]
            
            with patch('time.sleep'):
                with patch('job_sourcing.connectors.linkedin.parser.LinkedInGuestParser.fetch_job_details') as mock_details:
                    mock_details.return_value = {'description': 'Test', 'company': 'Test Co', 'location': 'NY'}
                    
                    offers = connector.fetch_offers(job_source, "test")
                    
                    # Should fetch all 75 jobs across 3 pages
                    assert len(offers) == 75
        
        finally:
            if original_max:
                os.environ['LINKEDIN_MAX_JOBS'] = original_max
            else:
                os.environ.pop('LINKEDIN_MAX_JOBS', None)
            if original_page:
                os.environ['LINKEDIN_PAGE_SIZE'] = original_page
            else:
                os.environ.pop('LINKEDIN_PAGE_SIZE', None)
    
    @patch('requests.get')
    def test_pagination_empty_second_page(self, mock_get, linkedin_connector, job_source):
        """Test pagination stops when second page is empty."""
        import os
        original_max = os.environ.get('LINKEDIN_MAX_JOBS')
        original_page = os.environ.get('LINKEDIN_PAGE_SIZE')
        
        try:
            os.environ['LINKEDIN_MAX_JOBS'] = '100'
            os.environ['LINKEDIN_PAGE_SIZE'] = '25'
            connector = LinkedInConnector()
            
            # First page returns 25 jobs, second page returns 0
            page1_html = self._generate_job_html(25, start_id=1)
            page2_html = "<div>No jobs</div>"
            
            mock_response1 = Mock()
            mock_response1.status_code = 200
            mock_response1.text = page1_html
            
            mock_response2 = Mock()
            mock_response2.status_code = 200
            mock_response2.text = page2_html
            
            mock_get.side_effect = [mock_response1, mock_response2]
            
            with patch('time.sleep'):
                with patch('job_sourcing.connectors.linkedin.parser.LinkedInGuestParser.fetch_job_details') as mock_details:
                    mock_details.return_value = {'description': 'Test', 'company': 'Test Co', 'location': 'NY'}
                    
                    offers = connector.fetch_offers(job_source, "test")
                    
                    # Should only fetch first page (25 jobs)
                    assert len(offers) == 25
        
        finally:
            if original_max:
                os.environ['LINKEDIN_MAX_JOBS'] = original_max
            else:
                os.environ.pop('LINKEDIN_MAX_JOBS', None)
            if original_page:
                os.environ['LINKEDIN_PAGE_SIZE'] = original_page
            else:
                os.environ.pop('LINKEDIN_PAGE_SIZE', None)
    
    @patch('requests.get')
    def test_pagination_max_jobs_reached(self, mock_get, linkedin_connector, job_source):
        """Test pagination stops when max_jobs is reached."""
        import os
        original_max = os.environ.get('LINKEDIN_MAX_JOBS')
        original_page = os.environ.get('LINKEDIN_PAGE_SIZE')
        
        try:
            os.environ['LINKEDIN_MAX_JOBS'] = '10'
            os.environ['LINKEDIN_PAGE_SIZE'] = '25'
            # Create NEW connector instance after setting env vars
            connector = LinkedInConnector()
            
            # First page returns 25 jobs (more than max_jobs)
            page1_html = self._generate_job_html(25, start_id=1)
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = page1_html
            
            mock_get.return_value = mock_response
            
            with patch('time.sleep'):
                with patch('job_sourcing.connectors.linkedin.parser.LinkedInGuestParser.fetch_job_details') as mock_details:
                    mock_details.return_value = {'description': 'Test', 'company': 'Test Co', 'location': 'NY'}
                    
                    offers = connector.fetch_offers(job_source, "test")
                    
                    # Should fetch 10 jobs (limited by max_jobs)
                    assert len(offers) == 10
        
        finally:
            if original_max:
                os.environ['LINKEDIN_MAX_JOBS'] = original_max
            else:
                os.environ.pop('LINKEDIN_MAX_JOBS', None)
            if original_page:
                os.environ['LINKEDIN_PAGE_SIZE'] = original_page
            else:
                os.environ.pop('LINKEDIN_PAGE_SIZE', None)
    
    @patch('requests.get')
    def test_pagination_page_failure(self, mock_get, linkedin_connector, job_source):
        """Test pagination stops on page request failure."""
        import os
        original_max = os.environ.get('LINKEDIN_MAX_JOBS')
        original_page = os.environ.get('LINKEDIN_PAGE_SIZE')
        
        try:
            os.environ['LINKEDIN_MAX_JOBS'] = '100'
            os.environ['LINKEDIN_PAGE_SIZE'] = '25'
            connector = LinkedInConnector()
            
            # First page succeeds, second page fails
            page1_html = self._generate_job_html(25, start_id=1)
            
            mock_response1 = Mock()
            mock_response1.status_code = 200
            mock_response1.text = page1_html
            
            mock_response2 = Mock()
            mock_response2.status_code = 503
            
            mock_get.side_effect = [mock_response1, mock_response2]
            
            with patch('time.sleep'):
                with patch('job_sourcing.connectors.linkedin.parser.LinkedInGuestParser.fetch_job_details') as mock_details:
                    mock_details.return_value = {'description': 'Test', 'company': 'Test Co', 'location': 'NY'}
                    
                    # Should raise LinkedInConnectorHTTPError on second page failure
                    with pytest.raises(LinkedInConnectorHTTPError):
                        linkedin_connector.fetch_offers(job_source, "test")
        
        finally:
            if original_max:
                os.environ['LINKEDIN_MAX_JOBS'] = original_max
            else:
                os.environ.pop('LINKEDIN_MAX_JOBS', None)
            if original_page:
                os.environ['LINKEDIN_PAGE_SIZE'] = original_page
            else:
                os.environ.pop('LINKEDIN_PAGE_SIZE', None)
    
    def _generate_job_html(self, count, start_id=1):
        """Helper to generate mock job HTML for pagination tests."""
        jobs_html = ""
        for i in range(count):
            job_id = start_id + i
            jobs_html += f"""
            <li>
              <div class="base-card relative w-full hover:no-underline focus:no-underline base-card--link base-search-card base-search-card--link job-search-card" data-entity-urn="urn:li:jobPosting:{job_id}">
                <a class="base-card__full-link absolute top-0 right-0 bottom-0 left-0 p-0 z-[2]" href="https://www.linkedin.com/jobs/view/job-{job_id}">
                  <span class="sr-only">Job {job_id}</span>
                </a>
                <div class="base-search-card__info">
                  <h3 class="base-search-card__title">Job {job_id}</h3>
                  <h4 class="base-search-card__subtitle">
                    <a class="hidden-nested-link" href="https://www.linkedin.com/company/test">Test Company</a>
                  </h4>
                  <div class="base-search-card__metadata">
                    <span class="job-search-card__location">Location</span>
                  </div>
                  <time class="job-search-card__listdate" datetime="2026-08-04">1 week ago</time>
                </div>
              </div>
            </li>
            """
        return jobs_html


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
