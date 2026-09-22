"""
Tests for LinkedIn Guest API Parser.
"""
import pytest
from unittest.mock import Mock, patch
import requests
from job_sourcing.connectors.linkedin.parser import LinkedInGuestParser
from job_sourcing.connectors.base import JobOfferDTO

def test_parse_search_response_success():
    """Test successful parsing of search response."""
    html = """
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
    
    jobs = LinkedInGuestParser.parse_search_response(html)
    
    assert len(jobs) == 1
    assert jobs[0]['job_id'] == '3952275643'
    assert jobs[0]['title'] == 'Python Developer'
    assert jobs[0]['company'] == 'Test Company'
    assert jobs[0]['location'] == 'New York, NY'
    assert jobs[0]['url'] == 'https://www.linkedin.com/jobs/view/python-developer-3952275643'
    assert jobs[0]['posted_date_raw'] == '2026-08-04'

def test_parse_search_response_missing_optional_fields():
    """Test parsing when optional fields are missing."""
    html = """
    <li>
      <div class="base-card relative w-full hover:no-underline focus:no-underline base-card--link base-search-card base-search-card--link job-search-card" data-entity-urn="urn:li:jobPosting:3952275643">
        <a class="base-card__full-link absolute top-0 right-0 bottom-0 left-0 p-0 z-[2]" href="https://www.linkedin.com/jobs/view/python-developer-3952275643">
          <span class="sr-only">Python Developer</span>
        </a>
        <div class="base-search-card__info">
          <h3 class="base-search-card__title">Python Developer</h3>
        </div>
      </div>
    </li>
    """
    
    jobs = LinkedInGuestParser.parse_search_response(html)
    
    assert len(jobs) == 1
    assert jobs[0]['job_id'] == '3952275643'
    assert jobs[0]['title'] == 'Python Developer'
    assert jobs[0]['company'] is None
    assert jobs[0]['location'] is None
    assert jobs[0]['posted_date_raw'] is None

def test_parse_search_response_empty():
    """Test parsing empty response."""
    html = "<div>No jobs here</div>"
    
    jobs = LinkedInGuestParser.parse_search_response(html)
    
    assert len(jobs) == 0

def test_parse_search_response_malformed():
    """Test parsing malformed HTML."""
    html = "Invalid HTML without proper structure"
    
    jobs = LinkedInGuestParser.parse_search_response(html)
    
    # Should not crash, just return empty list
    assert len(jobs) == 0

def test_parse_job_detail_success():
    """Test successful parsing of job detail response."""
    html = """
    <section class="show-more-less-html">
        <div class="show-more-less-html__markup">
            Job description here with Python skills.
        </div>
    </section>
    <a class="topcard__org-name-link">Test Company</a>
    <span class="topcard__flavor--bullet">New York, NY</span>
    <span class="posted-time-ago__text">1 week ago</span>
    """
    
    details = LinkedInGuestParser.parse_job_detail(html)
    
    assert details is not None
    assert 'Job description here with Python skills.' in details['description']
    assert details['company'] == 'Test Company'
    assert details['location'] == 'New York, NY'
    assert details['posted_date_raw'] == '1 week ago'

def test_map_to_job_offer_dto():
    """Test mapping parsed job data to JobOfferDTO."""
    job_data = {
        'job_id': '3952275643',
        'title': 'Python Developer',
        'company': 'Test Company',
        'location': 'New York, NY',
        'url': 'https://www.linkedin.com/jobs/view/python-developer-3952275643',
        'posted_date_raw': '2026-08-04',
        'description': 'Job description here'
    }
    
    dto = LinkedInGuestParser.map_to_job_offer_dto(job_data)
    
    assert isinstance(dto, JobOfferDTO)
    assert dto.raw_title == 'Python Developer'
    assert dto.raw_company == 'Test Company'
    assert dto.raw_location == 'New York, NY'
    assert dto.raw_description == 'Job description here'
    assert dto.raw_url == 'https://www.linkedin.com/jobs/view/python-developer-3952275643'
    assert dto.raw_posted_date == '2026-08-04'

def test_fetch_job_details_network_error():
    """Test network error handling when fetching job details."""
    with patch('requests.get') as mock_get:
        mock_get.side_effect = Exception("Network error")
        
        details = LinkedInGuestParser.fetch_job_details('3952275643')
        
        assert details is None

def test_fetch_job_details_http_error():
    """Test HTTP error handling when fetching job details."""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        details = LinkedInGuestParser.fetch_job_details('3952275643')
        
        assert details is None

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
