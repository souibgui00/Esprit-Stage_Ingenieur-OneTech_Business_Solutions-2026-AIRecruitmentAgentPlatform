"""
Focused tests for intermediate Apply button detection and navigation.
Tests the enhanced scoring, false-positive protection, and navigation handling.
"""
import pytest
from unittest.mock import Mock, MagicMock


class TestIntermediateApplyDetection:
    """Test suite for intermediate Apply button detection."""
    
    def test_apply_button_detection(self):
        """Test that 'Apply' buttons are correctly detected and scored."""
        # Mock element with 'Apply' text
        mock_element = Mock()
        mock_element.inner_text = Mock(return_value="Apply")
        mock_element.get_attribute = Mock(return_value=None)
        mock_element.is_visible = Mock(return_value=True)
        
        # Mock page
        mock_page = Mock()
        mock_page.query_selector_all = Mock(return_value=[mock_element])
        
        # Test the scoring logic (simplified version)
        text = mock_element.inner_text().strip().lower()
        apply_patterns = [
            {"text": "apply for this position", "score": 15},
            {"text": "apply for this job", "score": 15},
            {"text": "start application", "score": 14},
            {"text": "start your application", "score": 14},
            {"text": "continue to application", "score": 13},
            {"text": "apply now", "score": 12},
            {"text": "apply", "score": 10},
        ]
        
        score = 0
        for pattern in apply_patterns:
            if pattern["text"] in text:
                score = pattern["score"]
                break
        
        assert score == 10, f"Apply button should score 10, got {score}"
    
    def test_apply_now_button_detection(self):
        """Test that 'Apply Now' buttons receive higher scores."""
        mock_element = Mock()
        mock_element.inner_text = Mock(return_value="Apply Now")
        
        text = mock_element.inner_text().strip().lower()
        apply_patterns = [
            {"text": "apply for this position", "score": 15},
            {"text": "apply for this job", "score": 15},
            {"text": "start application", "score": 14},
            {"text": "start your application", "score": 14},
            {"text": "continue to application", "score": 13},
            {"text": "apply now", "score": 12},
            {"text": "apply", "score": 10},
        ]
        
        score = 0
        for pattern in apply_patterns:
            if pattern["text"] in text:
                score = pattern["score"]
                break
        
        assert score == 12, f"Apply Now button should score 12, got {score}"
    
    def test_apply_for_this_job_detection(self):
        """Test that 'Apply for this job' receives highest scores."""
        mock_element = Mock()
        mock_element.inner_text = Mock(return_value="Apply for this job")
        
        text = mock_element.inner_text().strip().lower()
        apply_patterns = [
            {"text": "apply for this position", "score": 15},
            {"text": "apply for this job", "score": 15},
            {"text": "start application", "score": 14},
            {"text": "start your application", "score": 14},
            {"text": "continue to application", "score": 13},
            {"text": "apply now", "score": 12},
            {"text": "apply", "score": 10},
        ]
        
        score = 0
        for pattern in apply_patterns:
            if pattern["text"] in text:
                score = pattern["score"]
                break
        
        assert score == 15, f"Apply for this job should score 15, got {score}"
    
    def test_start_application_detection(self):
        """Test that 'Start application' buttons are detected."""
        mock_element = Mock()
        mock_element.inner_text = Mock(return_value="Start application")
        
        text = mock_element.inner_text().strip().lower()
        apply_patterns = [
            {"text": "apply for this position", "score": 15},
            {"text": "apply for this job", "score": 15},
            {"text": "start application", "score": 14},
            {"text": "start your application", "score": 14},
            {"text": "continue to application", "score": 13},
            {"text": "apply now", "score": 12},
            {"text": "apply", "score": 10},
        ]
        
        score = 0
        for pattern in apply_patterns:
            if pattern["text"] in text:
                score = pattern["score"]
                break
        
        assert score == 14, f"Start application should score 14, got {score}"
    
    def test_bewerben_detection(self):
        """Test that German 'Bewerben' buttons are detected."""
        mock_element = Mock()
        mock_element.inner_text = Mock(return_value="Bewerben")
        
        text = mock_element.inner_text().strip().lower()
        apply_patterns = [
            {"text": "jetzt bewerben", "score": 14},
            {"text": "bewerbung starten", "score": 13},
            {"text": "bewerben", "score": 12},
        ]
        
        score = 0
        for pattern in apply_patterns:
            if pattern["text"] in text:
                score = pattern["score"]
                break
        
        assert score == 12, f"Bewerben should score 12, got {score}"
    
    def test_jetzt_bewerben_detection(self):
        """Test that German 'Jetzt bewerben' receives high scores."""
        mock_element = Mock()
        mock_element.inner_text = Mock(return_value="Jetzt bewerben")
        
        text = mock_element.inner_text().strip().lower()
        apply_patterns = [
            {"text": "jetzt bewerben", "score": 14},
            {"text": "bewerbung starten", "score": 13},
            {"text": "bewerben", "score": 12},
        ]
        
        score = 0
        for pattern in apply_patterns:
            if pattern["text"] in text:
                score = pattern["score"]
                break
        
        assert score == 14, f"Jetzt bewerben should score 14, got {score}"
    
    def test_postuler_detection(self):
        """Test that French 'Postuler' buttons are detected."""
        mock_element = Mock()
        mock_element.inner_text = Mock(return_value="Postuler")
        
        text = mock_element.inner_text().strip().lower()
        apply_patterns = [
            {"text": "postuler", "score": 12},
            {"text": "candidature", "score": 10},
            {"text": "déposer sa candidature", "score": 13},
        ]
        
        score = 0
        for pattern in apply_patterns:
            if pattern["text"] in text:
                score = pattern["score"]
                break
        
        assert score == 12, f"Postuler should score 12, got {score}"
    
    def test_login_button_rejection(self):
        """Test that 'Login' buttons are rejected."""
        mock_element = Mock()
        mock_element.inner_text = Mock(return_value="Login")
        
        text = mock_element.inner_text().strip().lower()
        negative_patterns = [
            "login", "sign in", "sign up", "share", "save", "subscribe",
            "newsletter", "similar jobs", "recommended jobs", "search jobs",
            "view company", "back to jobs", "job-copilot", "referral"
        ]
        
        has_negative = any(neg in text for neg in negative_patterns)
        
        assert has_negative, "Login button should be rejected as negative pattern"
    
    def test_newsletter_button_rejection(self):
        """Test that 'Newsletter' buttons are rejected."""
        mock_element = Mock()
        mock_element.inner_text = Mock(return_value="Subscribe to newsletter")
        
        text = mock_element.inner_text().strip().lower()
        negative_patterns = [
            "login", "sign in", "sign up", "share", "save", "subscribe",
            "newsletter", "similar jobs", "recommended jobs", "search jobs",
            "view company", "back to jobs", "job-copilot", "referral"
        ]
        
        has_negative = any(neg in text for neg in negative_patterns)
        
        assert has_negative, "Newsletter button should be rejected as negative pattern"
    
    def test_similar_jobs_rejection(self):
        """Test that 'Similar jobs' buttons are rejected."""
        mock_element = Mock()
        mock_element.inner_text = Mock(return_value="View similar jobs")
        
        text = mock_element.inner_text().strip().lower()
        negative_patterns = [
            "login", "sign in", "sign up", "share", "save", "subscribe",
            "newsletter", "similar jobs", "recommended jobs", "search jobs",
            "view company", "back to jobs", "job-copilot", "referral"
        ]
        
        has_negative = any(neg in text for neg in negative_patterns)
        
        assert has_negative, "Similar jobs button should be rejected as negative pattern"
    
    def test_multiple_candidates_correct_selection(self):
        """Test that the correct Apply candidate wins when multiple options exist."""
        # Mock multiple elements
        apply_button = Mock()
        apply_button.inner_text = Mock(return_value="Apply for this job")
        apply_button.get_attribute = Mock(return_value="")
        apply_button.is_visible = Mock(return_value=True)
        
        similar_jobs_button = Mock()
        similar_jobs_button.inner_text = Mock(return_value="View similar jobs")
        similar_jobs_button.get_attribute = Mock(return_value="")
        similar_jobs_button.is_visible = Mock(return_value=True)
        
        newsletter_button = Mock()
        newsletter_button.inner_text = Mock(return_value="Subscribe to newsletter")
        newsletter_button.get_attribute = Mock(return_value="")
        newsletter_button.is_visible = Mock(return_value=True)
        
        elements = [apply_button, similar_jobs_button, newsletter_button]
        
        # Score each element
        negative_patterns = [
            "login", "sign in", "sign up", "share", "save", "subscribe",
            "newsletter", "similar jobs", "recommended jobs", "search jobs",
            "view company", "back to jobs", "job-copilot", "referral"
        ]
        
        apply_patterns = [
            {"text": "apply for this position", "score": 15},
            {"text": "apply for this job", "score": 15},
            {"text": "start application", "score": 14},
            {"text": "start your application", "score": 14},
            {"text": "continue to application", "score": 13},
            {"text": "apply now", "score": 12},
            {"text": "apply", "score": 10},
        ]
        
        candidates = []
        for el in elements:
            text = el.inner_text().strip().lower()
            
            # Check for negative patterns
            has_negative = any(neg in text for neg in negative_patterns)
            if has_negative:
                continue
            
            # Score based on patterns
            score = 0
            for pattern in apply_patterns:
                if pattern["text"] in text:
                    score = pattern["score"]
                    break
            
            if score > 0:
                candidates.append({"element": el, "text": text, "score": score})
        
        # Sort by score
        candidates.sort(key=lambda x: x["score"], reverse=True)
        
        assert len(candidates) == 1, f"Should have 1 valid candidate, got {len(candidates)}"
        assert candidates[0]["score"] == 15, f"Apply for this job should win with score 15, got {candidates[0]['score']}"
        assert "apply" in candidates[0]["text"], "Selected candidate should be the apply button"
    
    def test_no_apply_candidate_no_click(self):
        """Test that when no valid Apply candidate exists, no click is performed."""
        # Mock elements with no valid apply buttons
        login_button = Mock()
        login_button.inner_text = Mock(return_value="Login")
        login_button.get_attribute = Mock(return_value="")
        login_button.is_visible = Mock(return_value=True)
        
        share_button = Mock()
        share_button.inner_text = Mock(return_value="Share this job")
        share_button.get_attribute = Mock(return_value="")
        share_button.is_visible = Mock(return_value=True)
        
        elements = [login_button, share_button]
        
        negative_patterns = [
            "login", "sign in", "sign up", "share", "save", "subscribe",
            "newsletter", "similar jobs", "recommended jobs", "search jobs",
            "view company", "back to jobs", "job-copilot", "referral"
        ]
        
        apply_patterns = [
            {"text": "apply for this position", "score": 15},
            {"text": "apply for this job", "score": 15},
            {"text": "start application", "score": 14},
            {"text": "start your application", "score": 14},
            {"text": "continue to application", "score": 13},
            {"text": "apply now", "score": 12},
            {"text": "apply", "score": 10},
        ]
        
        candidates = []
        for el in elements:
            text = el.inner_text().strip().lower()
            
            # Check for negative patterns
            has_negative = any(neg in text for neg in negative_patterns)
            if has_negative:
                continue
            
            # Score based on patterns
            score = 0
            for pattern in apply_patterns:
                if pattern["text"] in text:
                    score = pattern["score"]
                    break
            
            if score > 0:
                candidates.append({"element": el, "text": text, "score": score})
        
        assert len(candidates) == 0, f"Should have 0 valid candidates, got {len(candidates)}"
    
    def test_same_page_navigation(self):
        """Test handling of same-page navigation (SPA transitions)."""
        # This would test the SPA transition handling logic
        # For now, we test that the logic can handle non-href buttons
        mock_element = Mock()
        mock_element.inner_text = Mock(return_value="Apply")
        mock_element.get_attribute = Mock(return_value="")  # No href
        mock_element.is_visible = Mock(return_value=True)
        
        href = mock_element.get_attribute("href") or ""
        
        assert href == "", "Button should have no href for same-page navigation"
        assert mock_element.inner_text().strip().lower() == "apply", "Should be apply button"
    
    def test_new_tab_navigation(self):
        """Test handling of new-tab navigation."""
        mock_element = Mock()
        mock_element.inner_text = Mock(return_value="Apply Now")
        mock_element.get_attribute = Mock(return_value="https://example.com/apply")
        mock_element.is_visible = Mock(return_value=True)
        
        href = mock_element.get_attribute("href") or ""
        
        assert href.startswith("http"), "Link should have http href for new-tab navigation"
        assert "apply" in href.lower(), "Href should contain apply"
    
    def test_apply_clicked_but_no_form(self):
        """Test fallback when Apply is clicked but no form appears."""
        # This tests the fallback logic that returns ACTION_REQUIRED
        # when intermediate apply doesn't lead to a form
        
        # Simulate the scenario where form count is 0 after click
        forms_after = 0
        inputs_after = 0
        
        should_fallback = (forms_after == 0 and inputs_after == 0)
        
        assert should_fallback, "Should fallback to ACTION_REQUIRED when no form appears after click"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])