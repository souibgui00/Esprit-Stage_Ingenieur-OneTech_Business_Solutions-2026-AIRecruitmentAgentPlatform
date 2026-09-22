"""
Unit tests for previously untested connectors: Arbeitnow, Jobicy, TheMuse, Bundesagentur, WelcomeToTheJungle.
All tests use mocked HTTP responses to avoid dependencies on external services.
"""
import pytest
from unittest.mock import Mock, patch
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from job_sourcing.connectors.arbeitnow.connector import ArbeitnowConnector
from job_sourcing.connectors.jobicy.connector import JobicyConnector
from job_sourcing.connectors.themuse.connector import TheMuseConnector
from job_sourcing.connectors.bundesagentur.connector import BundesagenturConnector
from job_sourcing.connectors.welcometothejungle.algolia_connector import WelcomeToTheJungleAlgoliaConnector
from job_sourcing.models import JobSource, SourceType
from job_sourcing.connectors.base import JobOfferDTO


@pytest.fixture(autouse=True)
def cleanup_test_data():
    """No database cleanup needed for connector-only tests."""
    yield


# ==================== ARBEITNOW CONNECTOR TESTS ====================

def test_arbeitnow_connector_is_available():
    """Test Arbeitnow connector availability check (mocked)."""
    connector = ArbeitnowConnector()
    
    with patch('job_sourcing.connectors.arbeitnow.connector.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        assert connector.is_available() is True


def test_arbeitnow_connector_is_unavailable():
    """Test Arbeitnow connector when API is unavailable."""
    connector = ArbeitnowConnector()
    
    with patch('job_sourcing.connectors.arbeitnow.connector.requests.get') as mock_get:
        mock_get.side_effect = Exception("Network error")
        
        assert connector.is_available() is False


def test_arbeitnow_connector_fetch_offers():
    """Test Arbeitnow connector fetch_offers with mocked response."""
    connector = ArbeitnowConnector()
    source = JobSource(
        name="arbeitnow",
        type=SourceType.OFFICIAL_API,
        base_url="https://www.arbeitnow.com/api/job-board-api",
        is_active=True
    )
    
    mock_response_data = {
        "data": [
            {
                "title": "Python Developer",
                "company_name": "Test Company",
                "location": "Berlin",
                "description": "Python skills required",
                "url": "https://example.com/job/1",
                "created_at": "2024-01-01",
                "remote": True
            }
        ]
    }
    
    with patch('job_sourcing.connectors.arbeitnow.connector.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_get.return_value = mock_response
        
        offers = connector.fetch_offers(source, "python")
        
        # Arbeitnow fetches 2 pages (1 and 2), so we get duplicates if both pages return same data
        # In real scenario, pages would have different data
        assert len(offers) >= 1
        assert offers[0].raw_title == "Python Developer"
        assert offers[0].raw_company == "Test Company"


def test_arbeitnow_connector_keyword_filtering():
    """Test that Arbeitnow connector filters by keywords."""
    connector = ArbeitnowConnector()
    source = JobSource(
        name="arbeitnow",
        type=SourceType.OFFICIAL_API,
        base_url="https://www.arbeitnow.com/api/job-board-api",
        is_active=True
    )
    
    mock_response_data = {
        "data": [
            {
                "title": "Python Developer",
                "company_name": "Tech Corp",
                "location": "Remote",
                "description": "Python Django skills",
                "url": "https://example.com/job/1",
                "tags": ["python", "django"]
            },
            {
                "title": "Java Developer",
                "company_name": "Java Corp",
                "location": "Remote",
                "description": "Java Spring skills",
                "url": "https://example.com/job/2",
                "tags": ["java", "spring"]
            }
        ]
    }
    
    with patch('job_sourcing.connectors.arbeitnow.connector.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_get.return_value = mock_response
        
        offers = connector.fetch_offers(source, "python")
        
        # Should return Python-related jobs (may have duplicates from pagination)
        assert len(offers) >= 1
        assert all("python" in offer.raw_title.lower() or "python" in offer.raw_description.lower() for offer in offers)


def test_arbeitnow_connector_pagination():
    """Test Arbeitnow connector pagination across multiple pages."""
    connector = ArbeitnowConnector()
    source = JobSource(
        name="arbeitnow",
        type=SourceType.OFFICIAL_API,
        base_url="https://www.arbeitnow.com/api/job-board-api",
        is_active=True
    )
    
    # Mock responses for page 1 and page 2
    page1_data = {"data": [{"title": "Job 1", "company_name": "Company 1", "location": "Remote", "description": "Desc", "url": "url1"}]}
    page2_data = {"data": []}  # Empty page 2
    
    with patch('job_sourcing.connectors.arbeitnow.connector.requests.get') as mock_get:
        mock_response1 = Mock()
        mock_response1.status_code = 200
        mock_response1.json.return_value = page1_data
        
        mock_response2 = Mock()
        mock_response2.status_code = 200
        mock_response2.json.return_value = page2_data
        
        mock_get.side_effect = [mock_response1, mock_response2]
        
        offers = connector.fetch_offers(source, "developer")
        
        # Should fetch page 1, then stop when page 2 is empty
        # Note: If keyword doesn't match, returns empty list
        assert mock_get.call_count == 2  # Should try both pages


# ==================== JOBICY CONNECTOR TESTS ====================

def test_jobicy_connector_is_available():
    """Test Jobicy connector availability check (mocked)."""
    connector = JobicyConnector()
    
    with patch('job_sourcing.connectors.jobicy.connector.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        assert connector.is_available() is True


def test_jobicy_connector_fetch_offers():
    """Test Jobicy connector fetch_offers with mocked response."""
    connector = JobicyConnector()
    source = JobSource(
        name="jobicy",
        type=SourceType.OFFICIAL_API,
        base_url="https://jobicy.com/api/v2/remote-jobs",
        is_active=True
    )
    
    mock_response_data = {
        "jobs": [
            {
                "jobTitle": "React Developer",
                "companyName": "React Corp",
                "jobGeo": "Remote",
                "jobDescription": "React skills required",
                "url": "https://example.com/job/1",
                "pubDate": "2024-01-01"
            }
        ]
    }
    
    with patch('job_sourcing.connectors.jobicy.connector.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_get.return_value = mock_response
        
        offers = connector.fetch_offers(source, "react")
        
        assert len(offers) == 1
        assert offers[0].raw_title == "React Developer"
        assert offers[0].raw_company == "React Corp"


def test_jobicy_connector_keyword_filtering():
    """Test that Jobicy connector filters by keywords."""
    connector = JobicyConnector()
    source = JobSource(
        name="jobicy",
        type=SourceType.OFFICIAL_API,
        base_url="https://jobicy.com/api/v2/remote-jobs",
        is_active=True
    )
    
    mock_response_data = {
        "jobs": [
            {
                "jobTitle": "Python Developer",
                "companyName": "Python Corp",
                "jobGeo": "Remote",
                "jobDescription": "Python Django skills",
                "url": "https://example.com/job/1"
            },
            {
                "jobTitle": "Java Developer",
                "companyName": "Java Corp",
                "jobGeo": "Remote",
                "jobDescription": "Java Spring skills",
                "url": "https://example.com/job/2"
            }
        ]
    }
    
    with patch('job_sourcing.connectors.jobicy.connector.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_get.return_value = mock_response
        
        offers = connector.fetch_offers(source, "python")
        
        # Should only return Python-related job
        assert len(offers) == 1
        assert "python" in offers[0].raw_title.lower()


# ==================== THEMUSE CONNECTOR TESTS ====================

def test_themuse_connector_is_available():
    """Test TheMuse connector availability check (mocked)."""
    connector = TheMuseConnector()
    
    with patch('job_sourcing.connectors.themuse.connector.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        assert connector.is_available() is True


def test_themuse_connector_fetch_offers():
    """Test TheMuse connector fetch_offers with mocked response."""
    connector = TheMuseConnector()
    source = JobSource(
        name="themuse",
        type=SourceType.OFFICIAL_API,
        base_url="https://www.themuse.com/api/public/jobs",
        is_active=True
    )
    
    mock_response_data = {
        "results": [
            {
                "name": "Software Engineer",
                "company": {"name": "Tech Company"},
                "contents": "Python and Django skills required",
                "refs": {"landing_page": "https://example.com/job/1"},
                "locations": [{"name": "Remote"}],
                "publication_date": "2024-01-01"
            }
        ]
    }
    
    with patch('job_sourcing.connectors.themuse.connector.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_get.return_value = mock_response
        
        offers = connector.fetch_offers(source, "software")
        
        # TheMuse fetches from multiple categories (6 categories)
        # So we may get duplicates if all categories return same mock data
        assert len(offers) >= 1
        assert offers[0].raw_title == "Software Engineer"
        assert offers[0].raw_company == "Tech Company"


def test_themuse_connector_multiple_categories():
    """Test TheMuse connector fetching from multiple categories."""
    connector = TheMuseConnector()
    source = JobSource(
        name="themuse",
        type=SourceType.OFFICIAL_API,
        base_url="https://www.themuse.com/api/public/jobs",
        is_active=True
    )
    
    # Mock responses for different categories
    mock_response_data = {
        "results": [
            {
                "name": "Engineer",
                "company": {"name": "Company"},
                "contents": "Engineering role",
                "refs": {"landing_page": "https://example.com/job/1"},
                "locations": [{"name": "Remote"}]
            }
        ]
    }
    
    with patch('job_sourcing.connectors.themuse.connector.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_get.return_value = mock_response
        
        offers = connector.fetch_offers(source, "engineer")
        
        # Should fetch from multiple categories (CATEGORIES list has 6 items)
        assert mock_get.call_count == 6  # One call per category


# ==================== BUNDESAGENTUR CONNECTOR TESTS ====================

def test_bundesagentur_connector_is_available():
    """Test Bundesagentur connector availability check (mocked)."""
    connector = BundesagenturConnector()
    
    with patch('job_sourcing.connectors.bundesagentur.connector.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        assert connector.is_available() is True


def test_bundesagentur_connector_fetch_offers():
    """Test Bundesagentur connector fetch_offers with mocked response."""
    connector = BundesagenturConnector()
    source = JobSource(
        name="bundesagentur",
        type=SourceType.OFFICIAL_API,
        base_url="https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/app/jobs",
        is_active=True
    )
    
    mock_response_data = {
        "stellenangebote": [
            {
                "titel": "Softwareentwickler",
                "arbeitgeber": "German Company",
                "arbeitsort": {
                    "ort": "Berlin",
                    "land": "Deutschland"
                },
                "refnr": "12345",
                "beruf": "Software Development",
                "modifikationsTimestamp": "2024-01-01T00:00:00"
            }
        ]
    }
    
    with patch('job_sourcing.connectors.bundesagentur.connector.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_get.return_value = mock_response
        
        offers = connector.fetch_offers(source, "developer")
        
        assert len(offers) == 1
        assert offers[0].raw_title == "Softwareentwickler"
        assert offers[0].raw_company == "German Company"


def test_bundesagentur_connector_url_construction():
    """Test Bundesagentur connector constructs correct URLs."""
    connector = BundesagenturConnector()
    source = JobSource(
        name="bundesagentur",
        type=SourceType.OFFICIAL_API,
        base_url="https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/app/jobs",
        is_active=True
    )
    
    mock_response_data = {
        "stellenangebote": [
            {
                "titel": "Developer",
                "arbeitgeber": "Company",
                "arbeitsort": {"ort": "Munich", "land": "Deutschland"},
                "refnr": "67890",
                "beruf": "Development"
            }
        ]
    }
    
    with patch('job_sourcing.connectors.bundesagentur.connector.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_get.return_value = mock_response
        
        offers = connector.fetch_offers(source, "developer")
        
        # URL should be constructed from refnr
        assert "67890" in offers[0].raw_url
        assert "arbeitsagentur.de" in offers[0].raw_url


# ==================== WELCOME TO THE JUNGLE CONNECTOR TESTS ====================

def test_wttj_connector_is_available():
    """Test WelcomeToTheJungle connector availability check (mocked)."""
    connector = WelcomeToTheJungleAlgoliaConnector()
    
    with patch('job_sourcing.connectors.welcometothejungle.algolia_connector.requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        assert connector.is_available() is True


def test_wttj_connector_fetch_offers():
    """Test WelcomeToTheJungle connector fetch_offers with mocked response."""
    connector = WelcomeToTheJungleAlgoliaConnector()
    source = JobSource(
        name="welcometothejungle",
        type=SourceType.OFFICIAL_API,
        base_url="https://www.welcometothejungle.com",
        is_active=True
    )
    
    mock_response_data = {
        "hits": [
            {
                "name": "Data Scientist",
                "organization": {
                    "name": "Data Company",
                    "slug": "data-company"
                },
                "slug": "data-scientist-role",
                "objectID": "12345",
                "office": {
                    "city": "Paris",
                    "country": "France"
                },
                "remote": "full",
                "contract_type_names": {"fr": "CDI"},
                "profession": {"name": {"fr": "Data Science"}},
                "sectors": [{"name": {"fr": "Tech"}}],
                "published_at": "2024-01-01T00:00:00.000+01:00"
            }
        ]
    }
    
    with patch('job_sourcing.connectors.welcometothejungle.algolia_connector.requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_post.return_value = mock_response
        
        offers = connector.fetch_offers(source, "data")
        
        assert len(offers) == 1
        assert offers[0].raw_title == "Data Scientist"
        assert offers[0].raw_company == "Data Company"


def test_wttj_connector_remote_detection():
    """Test WelcomeToTheJungle connector correctly detects remote jobs."""
    connector = WelcomeToTheJungleAlgoliaConnector()
    source = JobSource(
        name="welcometothejungle",
        type=SourceType.OFFICIAL_API,
        base_url="https://www.welcometothejungle.com",
        is_active=True
    )
    
    # Test full remote
    mock_full_remote = {
        "hits": [
            {
                "name": "Remote Job",
                "organization": {"name": "Remote Company", "slug": "remote-co"},
                "slug": "remote-job",
                "objectID": "1",
                "office": {"city": "Paris", "country": "France"},
                "remote": "full",
                "contract_type_names": {},
                "profession": {},
                "sectors": []
            }
        ]
    }
    
    with patch('job_sourcing.connectors.welcometothejungle.algolia_connector.requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_full_remote
        mock_post.return_value = mock_response
        
        offers = connector.fetch_offers(source, "remote")
        
        assert "Remote" in offers[0].raw_location


def test_wttj_connector_url_construction():
    """Test WelcomeToTheJungle connector constructs correct URLs."""
    connector = WelcomeToTheJungleAlgoliaConnector()
    source = JobSource(
        name="welcometothejungle",
        type=SourceType.OFFICIAL_API,
        base_url="https://www.welcometothejungle.com",
        is_active=True
    )
    
    mock_response_data = {
        "hits": [
            {
                "name": "Developer",
                "organization": {
                    "name": "Tech Company",
                    "slug": "tech-company"
                },
                "slug": "developer-role",
                "objectID": "999",
                "office": {},
                "remote": "",
                "contract_type_names": {},
                "profession": {},
                "sectors": []
            }
        ]
    }
    
    with patch('job_sourcing.connectors.welcometothejungle.algolia_connector.requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_post.return_value = mock_response
        
        offers = connector.fetch_offers(source, "developer")
        
        # URL should contain company slug and job slug
        assert "tech-company" in offers[0].raw_url
        assert "developer-role" in offers[0].raw_url


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
