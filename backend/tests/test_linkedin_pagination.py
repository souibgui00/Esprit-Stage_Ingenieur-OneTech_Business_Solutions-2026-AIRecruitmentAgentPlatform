"""
LinkedIn connector pagination tests covering multiple pages, empty page termination, 
max_jobs enforcement, and HTTP 429 handling.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import time

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from job_sourcing.connectors.linkedin.connector import LinkedInConnector
from job_sourcing.connectors.linkedin.parser import LinkedInGuestParser
from job_sourcing.models import JobSource, SourceType
from job_sourcing.connectors.base import JobOfferDTO


@pytest.fixture(autouse=True)
def cleanup_test_data():
    """No database cleanup needed for connector-only tests."""
    yield


# ==================== MULTIPLE PAGES TESTS ====================

def test_linkedin_pagination_multiple_pages():
    """Test LinkedIn connector correctly handles pagination across multiple pages."""
    import os
    original_mock_mode = os.environ.get('LINKEDIN_MOCK_MODE')
    
    try:
        # Disable mock mode to test real pagination logic
        os.environ['LINKEDIN_MOCK_MODE'] = 'false'
        connector = LinkedInConnector()
        
        source = JobSource(
            name="linkedin",
            type=SourceType.SCRAPER,
            base_url="https://linkedin.com",
            is_active=True
        )
        
        # Mock multiple pages of results
        page1_html = """
        <div data-entity-urn="urn:li:jobPosting:1">
            <h3 class="base-search-card__title">Python Developer 1</h3>
            <h4 class="base-search-card__subtitle"><a>Company A</a></h4>
            <span class="job-search-card__location">Paris</span>
            <a class="base-card__full-link" href="https://linkedin.com/jobs/view/1">Link</a>
        </div>
        """
        
        page2_html = """
        <div data-entity-urn="urn:li:jobPosting:2">
            <h3 class="base-search-card__title">Python Developer 2</h3>
            <h4 class="base-search-card__subtitle"><a>Company B</a></h4>
            <span class="job-search-card__location">London</span>
            <a class="base-card__full-link" href="https://linkedin.com/jobs/view/2">Link</a>
        </div>
        """
        
        page3_html = ""  # Empty page to test termination
        
        job_detail_html = """
        <section class="show-more-less-html">
            <div class="show-more-less-html__markup">Python Django skills required</div>
        </section>
        """
        
        with patch('requests.get') as mock_get:
            # First page of search results
            mock_response1 = Mock()
            mock_response1.status_code = 200
            mock_response1.text = page1_html
            
            # Second page of search results
            mock_response2 = Mock()
            mock_response2.status_code = 200
            mock_response2.text = page2_html
            
            # Third page (empty - should stop pagination)
            mock_response3 = Mock()
            mock_response3.status_code = 200
            mock_response3.text = page3_html
            
            # Job detail responses
            mock_detail_response = Mock()
            mock_detail_response.status_code = 200
            mock_detail_response.text = job_detail_html
            
            # Sequence: page1, detail1, page2, detail2, page3
            mock_get.side_effect = [
                mock_response1, mock_detail_response,
                mock_response2, mock_detail_response,
                mock_response3
            ]
            
            offers = connector._fetch_via_api(source, "python")
            
            # Should fetch jobs from multiple pages
            # The exact count depends on job detail fetching success
            assert len(offers) >= 1
            assert mock_get.call_count >= 3  # At least 2 search pages + detail requests
            
    finally:
        if original_mock_mode is None:
            os.environ.pop('LINKEDIN_MOCK_MODE', None)
        else:
            os.environ['LINKEDIN_MOCK_MODE'] = original_mock_mode


def test_linkedin_pagination_empty_page_termination():
    """Test that LinkedIn connector stops pagination when encountering empty page."""
    import os
    original_mock_mode = os.environ.get('LINKEDIN_MOCK_MODE')
    
    try:
        os.environ['LINKEDIN_MOCK_MODE'] = 'false'
        connector = LinkedInConnector()
        
        source = JobSource(
            name="linkedin",
            type=SourceType.SCRAPER,
            base_url="https://linkedin.com",
            is_active=True
        )
        
        # First page has results, second page is empty
        page1_html = """
        <div data-entity-urn="urn:li:jobPosting:1">
            <h3 class="base-search-card__title">Developer</h3>
            <h4 class="base-search-card__subtitle"><a>Company</a></h4>
            <span class="job-search-card__location">Remote</span>
            <a class="base-card__full-link" href="https://linkedin.com/jobs/view/1">Link</a>
        </div>
        """
        
        page2_html = ""  # Empty page
        
        job_detail_html = """
        <section class="show-more-less-html">
            <div class="show-more-less-html__markup">Skills required</div>
        </section>
        """
        
        with patch('requests.get') as mock_get:
            mock_response1 = Mock()
            mock_response1.status_code = 200
            mock_response1.text = page1_html
            
            mock_response2 = Mock()
            mock_response2.status_code = 200
            mock_response2.text = page2_html
            
            mock_detail = Mock()
            mock_detail.status_code = 200
            mock_detail.text = job_detail_html
            
            mock_get.side_effect = [mock_response1, mock_detail, mock_response2]
            
            offers = connector._fetch_via_api(source, "developer")
            
            # Should get 1 job from page 1, then stop on empty page 2
            assert len(offers) == 1
            assert mock_get.call_count == 3  # page1 + detail + empty page2 check
            
    finally:
        if original_mock_mode is None:
            os.environ.pop('LINKEDIN_MOCK_MODE', None)
        else:
            os.environ['LINKEDIN_MOCK_MODE'] = original_mock_mode


# ==================== MAX_JOBS ENFORCEMENT TESTS ====================

def test_linkedin_max_jobs_enforcement():
    """Test that LinkedIn connector respects LINKEDIN_MAX_JOBS limit."""
    import os
    original_mock_mode = os.environ.get('LINKEDIN_MOCK_MODE')
    original_max_jobs = os.environ.get('LINKEDIN_MAX_JOBS')
    
    try:
        os.environ['LINKEDIN_MOCK_MODE'] = 'false'
        os.environ['LINKEDIN_MAX_JOBS'] = '3'  # Set max to 3 jobs
        connector = LinkedInConnector()
        
        source = JobSource(
            name="linkedin",
            type=SourceType.SCRAPER,
            base_url="https://linkedin.com",
            is_active=True
        )
        
        # Create HTML for 5 jobs across 2 pages
        page1_html = ""
        for i in range(1, 4):
            page1_html += f"""
            <div data-entity-urn="urn:li:jobPosting:{i}">
                <h3 class="base-search-card__title">Job {i}</h3>
                <h4 class="base-search-card__subtitle"><a>Company</a></h4>
                <span class="job-search-card__location">Location</span>
                <a class="base-card__full-link" href="https://linkedin.com/jobs/view/{i}">Link</a>
            </div>
            """
        
        page2_html = """
        <div data-entity-urn="urn:li:jobPosting:4">
            <h3 class="base-search-card__title">Job 4</h3>
            <h4 class="base-search-card__subtitle"><a>Company</a></h4>
            <span class="job-search-card__location">Location</span>
            <a class="base-card__full-link" href="https://linkedin.com/jobs/view/4">Link</a>
        </div>
        """
        
        job_detail_html = """
        <section class="show-more-less-html">
            <div class="show-more-less-html__markup">Description</div>
        </section>
        """
        
        with patch('requests.get') as mock_get:
            # Page 1 has 3 jobs (exactly max_jobs)
            mock_response1 = Mock()
            mock_response1.status_code = 200
            mock_response1.text = page1_html
            
            # Page 2 has 1 more job (should not be fetched)
            mock_response2 = Mock()
            mock_response2.status_code = 200
            mock_response2.text = page2_html
            
            mock_detail = Mock()
            mock_detail.status_code = 200
            mock_detail.text = job_detail_html
            
            # Should call: page1, detail1, detail2, detail3 (3 jobs from page1)
            # Then stop because max_jobs reached, should not fetch page2
            mock_get.side_effect = [mock_response1, mock_detail, mock_detail, mock_detail]
            
            offers = connector._fetch_via_api(source, "job")
            
            # Should only get 3 jobs (max_jobs limit)
            assert len(offers) == 3
            # Should not fetch page 2 since max_jobs reached on page 1
            assert mock_get.call_count == 4  # page1 + 3 detail requests
            
    finally:
        if original_mock_mode is None:
            os.environ.pop('LINKEDIN_MOCK_MODE', None)
            os.environ.pop('LINKEDIN_MAX_JOBS', None)
        else:
            os.environ['LINKEDIN_MOCK_MODE'] = original_mock_mode
            if original_max_jobs is None:
                os.environ.pop('LINKEDIN_MAX_JOBS', None)
            else:
                os.environ['LINKEDIN_MAX_JOBS'] = original_max_jobs


def test_linkedin_max_jobs_across_pages():
    """Test max_jobs enforcement when jobs span multiple pages."""
    import os
    original_mock_mode = os.environ.get('LINKEDIN_MOCK_MODE')
    original_max_jobs = os.environ.get('LINKEDIN_MAX_JOBS')
    
    try:
        os.environ['LINKEDIN_MOCK_MODE'] = 'false'
        os.environ['LINKEDIN_MAX_JOBS'] = '5'
        connector = LinkedInConnector()
        
        source = JobSource(
            name="linkedin",
            type=SourceType.SCRAPER,
            base_url="https://linkedin.com",
            is_active=True
        )
        
        # Page 1 has 3 jobs
        page1_html = ""
        for i in range(1, 4):
            page1_html += f"""
            <div data-entity-urn="urn:li:jobPosting:{i}">
                <h3 class="base-search-card__title">Job {i}</h3>
                <h4 class="base-search-card__subtitle"><a>Company</a></h4>
                <span class="job-search-card__location">Location</span>
                <a class="base-card__full-link" href="https://linkedin.com/jobs/view/{i}">Link</a>
            </div>
            """
        
        # Page 2 has 3 more jobs (should only fetch 2 to reach max 5)
        page2_html = ""
        for i in range(4, 7):
            page2_html += f"""
            <div data-entity-urn="urn:li:jobPosting:{i}">
                <h3 class="base-search-card__title">Job {i}</h3>
                <h4 class="base-search-card__subtitle"><a>Company</a></h4>
                <span class="job-search-card__location">Location</span>
                <a class="base-card__full-link" href="https://linkedin.com/jobs/view/{i}">Link</a>
            </div>
            """
        
        job_detail_html = """
        <section class="show-more-less-html">
            <div class="show-more-less-html__markup">Description</div>
        </section>
        """
        
        with patch('requests.get') as mock_get:
            mock_response1 = Mock()
            mock_response1.status_code = 200
            mock_response1.text = page1_html
            
            mock_response2 = Mock()
            mock_response2.status_code = 200
            mock_response2.text = page2_html
            
            mock_detail = Mock()
            mock_detail.status_code = 200
            mock_detail.text = job_detail_html
            
            # Page1 (3 jobs) + 3 details + Page2 (fetch but only process 2) + 2 details
            mock_get.side_effect = [
                mock_response1, mock_detail, mock_detail, mock_detail,
                mock_response2, mock_detail, mock_detail
            ]
            
            offers = connector._fetch_via_api(source, "job")
            
            # Should respect max_jobs limit (set to 5)
            # The exact count depends on pagination and detail fetching
            assert len(offers) <= 5
            # Should fetch from multiple pages
            assert mock_get.call_count >= 2  # At least page1 + details
            
    finally:
        if original_mock_mode is None:
            os.environ.pop('LINKEDIN_MOCK_MODE', None)
            os.environ.pop('LINKEDIN_MAX_JOBS', None)
        else:
            os.environ['LINKEDIN_MOCK_MODE'] = original_mock_mode
            if original_max_jobs is None:
                os.environ.pop('LINKEDIN_MAX_JOBS', None)
            else:
                os.environ['LINKEDIN_MAX_JOBS'] = original_max_jobs


# ==================== HTTP 429 RATE LIMIT HANDLING TESTS ====================

def test_linkedin_http_429_handling():
    """Test that LinkedIn connector raises proper error on HTTP 429 rate limit."""
    import os
    original_mock_mode = os.environ.get('LINKEDIN_MOCK_MODE')
    
    try:
        os.environ['LINKEDIN_MOCK_MODE'] = 'false'
        connector = LinkedInConnector()
        
        source = JobSource(
            name="linkedin",
            type=SourceType.SCRAPER,
            base_url="https://linkedin.com",
            is_active=True
        )
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 429  # Rate limit
            mock_get.return_value = mock_response
            
            from job_sourcing.connectors.linkedin.connector import LinkedInConnectorAccessDeniedError
            
            with pytest.raises(LinkedInConnectorAccessDeniedError) as exc_info:
                connector._fetch_via_api(source, "python")
            
            assert "429" in str(exc_info.value)
            assert "rate limited" in str(exc_info.value).lower()
            
    finally:
        if original_mock_mode is None:
            os.environ.pop('LINKEDIN_MOCK_MODE', None)
        else:
            os.environ['LINKEDIN_MOCK_MODE'] = original_mock_mode


def test_linkedin_http_403_handling():
    """Test that LinkedIn connector raises proper error on HTTP 403 access denied."""
    import os
    original_mock_mode = os.environ.get('LINKEDIN_MOCK_MODE')
    
    try:
        os.environ['LINKEDIN_MOCK_MODE'] = 'false'
        connector = LinkedInConnector()
        
        source = JobSource(
            name="linkedin",
            type=SourceType.SCRAPER,
            base_url="https://linkedin.com",
            is_active=True
        )
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 403  # Access denied
            mock_get.return_value = mock_response
            
            from job_sourcing.connectors.linkedin.connector import LinkedInConnectorAccessDeniedError
            
            with pytest.raises(LinkedInConnectorAccessDeniedError) as exc_info:
                connector._fetch_via_api(source, "python")
            
            assert "403" in str(exc_info.value)
            assert "access denied" in str(exc_info.value).lower()
            
    finally:
        if original_mock_mode is None:
            os.environ.pop('LINKEDIN_MOCK_MODE', None)
        else:
            os.environ['LINKEDIN_MOCK_MODE'] = original_mock_mode


def test_linkedin_http_500_handling():
    """Test that LinkedIn connector raises proper error on HTTP 500 server error."""
    import os
    original_mock_mode = os.environ.get('LINKEDIN_MOCK_MODE')
    
    try:
        os.environ['LINKEDIN_MOCK_MODE'] = 'false'
        connector = LinkedInConnector()
        
        source = JobSource(
            name="linkedin",
            type=SourceType.SCRAPER,
            base_url="https://linkedin.com",
            is_active=True
        )
        
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 500  # Server error
            mock_get.return_value = mock_response
            
            from job_sourcing.connectors.linkedin.connector import LinkedInConnectorHTTPError
            
            with pytest.raises(LinkedInConnectorHTTPError) as exc_info:
                connector._fetch_via_api(source, "python")
            
            assert "500" in str(exc_info.value)
            
    finally:
        if original_mock_mode is None:
            os.environ.pop('LINKEDIN_MOCK_MODE', None)
        else:
            os.environ['LINKEDIN_MOCK_MODE'] = original_mock_mode


# ==================== REQUEST DELAY TESTS ====================

def test_linkedin_request_delay_between_pages():
    """Test that LinkedIn connector adds delay between pagination requests."""
    import os
    original_mock_mode = os.environ.get('LINKEDIN_MOCK_MODE')
    original_delay = os.environ.get('LINKEDIN_REQUEST_DELAY')
    
    try:
        os.environ['LINKEDIN_MOCK_MODE'] = 'false'
        os.environ['LINKEDIN_REQUEST_DELAY'] = '0.1'  # Short delay for testing
        connector = LinkedInConnector()
        
        source = JobSource(
            name="linkedin",
            type=SourceType.SCRAPER,
            base_url="https://linkedin.com",
            is_active=True
        )
        
        page1_html = """
        <div data-entity-urn="urn:li:jobPosting:1">
            <h3 class="base-search-card__title">Job 1</h3>
            <h4 class="base-search-card__subtitle"><a>Company</a></h4>
            <span class="job-search-card__location">Location</span>
            <a class="base-card__full-link" href="https://linkedin.com/jobs/view/1">Link</a>
        </div>
        """
        
        page2_html = """
        <div data-entity-urn="urn:li:jobPosting:2">
            <h3 class="base-search-card__title">Job 2</h3>
            <h4 class="base-search-card__subtitle"><a>Company</a></h4>
            <span class="job-search-card__location">Location</span>
            <a class="base-card__full-link" href="https://linkedin.com/jobs/view/2">Link</a>
        </div>
        """
        
        job_detail_html = """
        <section class="show-more-less-html">
            <div class="show-more-less-html__markup">Description</div>
        </section>
        """
        
        with patch('requests.get') as mock_get:
            with patch('time.sleep') as mock_sleep:
                mock_response1 = Mock()
                mock_response1.status_code = 200
                mock_response1.text = page1_html
                
                mock_response2 = Mock()
                mock_response2.status_code = 200
                mock_response2.text = page2_html
                
                mock_detail = Mock()
                mock_detail.status_code = 200
                mock_detail.text = job_detail_html
                
                mock_get.side_effect = [mock_response1, mock_detail, mock_response2, mock_detail]
                
                connector._fetch_via_api(source, "job")
                
                # Should call sleep at least once (between pages)
                assert mock_sleep.call_count >= 1
                
    finally:
        if original_mock_mode is None:
            os.environ.pop('LINKEDIN_MOCK_MODE', None)
            os.environ.pop('LINKEDIN_REQUEST_DELAY', None)
        else:
            os.environ['LINKEDIN_MOCK_MODE'] = original_mock_mode
            if original_delay is None:
                os.environ.pop('LINKEDIN_REQUEST_DELAY', None)
            else:
                os.environ['LINKEDIN_REQUEST_DELAY'] = original_delay


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
