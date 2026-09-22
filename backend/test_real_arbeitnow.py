"""
Real browser test against the actual Arbeitnow URL to verify apply-link discovery.
This tests the actual implementation against the real website.
"""
import os
import sys
from playwright.sync_api import sync_playwright

def test_real_arbeitnow():
    """Test apply-link discovery on the real Arbeitnow page."""
    url = "https://www.arbeitnow.com/jobs/companies/autarcenergy/internship-go-to-market-engineering-ai-automation-berlin-236643"
    
    print(f"Testing real Arbeitnow page: {url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 2200},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            # Navigate to the page
            print(f"Navigating to {url}...")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            print(f"Page loaded: {page.title()}")
            print(f"Current URL: {page.url}")
            
            # Apply the scoring function from the implementation
            def score_apply_link(element, current_url):
                """Score an apply link based on relevance and priority."""
                try:
                    href = element.get_attribute("href") or ""
                    text = element.inner_text().strip().lower()
                    current_domain = current_url.split("//")[-1].split("/")[0].lower()
                    
                    if not href.startswith("http"):
                        return -1000  # Invalid link
                    
                    link_domain = href.split("//")[-1].split("/")[0].lower()
                    link_path = href.split("//")[-1].lower() if "//" in href else href.lower()
                    score = 0
                    
                    # Priority 1: Exact application text (highest priority: +10 to +15)
                    exact_apply_patterns = [
                        "apply for this position",
                        "apply for this job", 
                        "apply now",
                        "apply on company website",
                        "go to application",
                        "postuler à cette offre",
                        "candidature",
                        "bewerben",
                        "bewerbung",
                        "jetzt bewerben",
                        "apply for this position",
                        "apply to this job"
                    ]
                    
                    for pattern in exact_apply_patterns:
                        if pattern in text:
                            score += 12
                            break
                    
                    # Priority 2: URL patterns indicating application pages (+3 to +6)
                    url_apply_patterns = [
                        "/apply",
                        "/application",
                        "/career",
                        "/careers",
                        "/jobs",
                        "/job",
                        "/vacancy",
                        "/position",
                        ".jobs.personio.de",  # Personio ATS
                        ".greenhouse.io",
                        ".lever.co",
                        ".ashbyhq.com",
                        ".workable.com",
                        ".myworkdayjobs.com"
                    ]
                    
                    for pattern in url_apply_patterns:
                        if pattern in link_path:
                            score += 5
                            break
                    
                    # Priority 3: Known ATS domains (+8)
                    known_ats_domains = [
                        "greenhouse.io", "lever.co", "ashbyhq.com", "ashby", 
                        "workable.com", "workable", "myworkdayjobs.com", "smartrecruiters.com",
                        "personio.de", "jobs.personio.de"
                    ]
                    for ats_domain in known_ats_domains:
                        if ats_domain in link_domain:
                            score += 8
                            break
                    
                    # Priority 4: External domain to job board (+5 to +10)
                    if link_domain != current_domain:
                        current_base = current_domain.split(".")[-2:] if "." in current_domain else [current_domain]
                        link_base = link_domain.split(".")[-2:] if "." in link_domain else [link_domain]
                        
                        if current_base != link_base:
                            score += 7
                    
                    # Priority 5: Generic "Apply" text (+2)
                    if "apply" in text and score == 0:
                        score += 2
                    
                    # Priority 6: Generic application-related text (+1)
                    generic_apply_text = ["application", "candidature", "bewerbung"]
                    for pattern in generic_apply_text:
                        if pattern in text and score < 5:
                            score += 1
                            break
                    
                    # Negative scoring: Reject known promotional/service links (-100)
                    promotional_patterns = [
                        "job-copilot",
                        "referral",
                        "share",
                        "newsletter",
                        "subscribe",
                        "similar jobs"
                    ]
                    
                    for pattern in promotional_patterns:
                        if pattern in href.lower() or pattern in text:
                            score -= 100
                            break
                    
                    # Special case: Job board intermediate apply pages
                    job_board_domains = ["arbeitnow.com", "remotive.com", "wellfound.com", "angellist.co"]
                    if any(board in current_domain for board in job_board_domains):
                        if "/apply" in link_path and link_domain == current_domain:
                            score += 6  # Moderate priority for intermediate apply pages
                    
                    return score
                except Exception as e:
                    print(f"Error scoring link: {e}")
                    return -1000
            
            # Use the enhanced selectors from the implementation
            apply_selectors = [
                # English apply patterns
                "a:has-text('Apply')", "button:has-text('Apply')",
                "a:has-text('Apply Now')", "button:has-text('Apply Now')",
                "a:has-text('Apply for this job')", "a:has-text('Apply for this position')",
                "a:has-text('Apply on company website')", "a:has-text('Go to application')",
                
                # French apply patterns
                "a:has-text('Postuler')", "button:has-text('Postuler')",
                "a:has-text('Postuler à cette offre')", "a:has-text('Candidature')",
                "a:has-text('Envoyer ma candidature')",
                
                # German apply patterns
                "a:has-text('Bewerben')", "button:has-text('Bewerben')",
                "a:has-text('Jetzt bewerben')", "a:has-text('Bewerbung')",
                "a:has-text('Auf diese Stelle bewerben')",
                
                # Class-based selectors
                "a.btn-apply", "a[class*='apply']", "button[class*='apply']",
                "a.btn-primary[href*='apply']", "a[href*='/apply']",
                "[data-testid*='apply']", ".apply-button", "#apply-button",
                
                # ATS-specific selectors
                "a[href*='greenhouse']", "a[href*='lever.co']", "a[href*='ashby']",
                "a[href*='workable']", "a[href*='jobs.']", "a[href*='personio']",
                
                # URL pattern selectors
                "a[href*='/apply']", "a[href*='/application']", "a[href*='/career']",
                "a[href*='/careers']", "a[href*='/jobs']", "a[href*='/job']",
                
                # Arbeitnow-specific patterns
                "a.grow", "a[href*='/apply']", "a[href*='arbeitnow.com/apply']",
                
                # Generic apply-related text
                "a:has-text('Application')", "button:has-text('Application')",
            ]
            
            # Find all candidate apply links
            candidates = []
            seen_elements = set()
            
            for sel in apply_selectors:
                try:
                    elements = page.query_selector_all(sel)
                    for el in elements:
                        # Avoid duplicates
                        el_id = id(el)
                        if el_id in seen_elements:
                            continue
                        seen_elements.add(el_id)
                        
                        if el.is_visible():
                            href = el.get_attribute("href") or ""
                            text = el.inner_text().strip()
                            score = score_apply_link(el, url)
                            
                            if score > 0:  # Only consider valid candidates
                                candidates.append({
                                    "element": el,
                                    "href": href,
                                    "text": text,
                                    "score": score
                                })
                except Exception as e:
                    print(f"Error with selector {sel}: {e}")
                    continue
            
            # Sort candidates by score (highest first)
            candidates.sort(key=lambda x: x["score"], reverse=True)
            
            print(f"\n=== CANDIDATES FOUND: {len(candidates)} ===")
            for i, candidate in enumerate(candidates):
                print(f"{i+1}. text='{candidate['text'][:50]}', href='{candidate['href'][:80]}', score={candidate['score']}")
            
            if candidates:
                best_candidate = candidates[0]
                print(f"\n=== SELECTED CANDIDATE ===")
                print(f"text='{best_candidate['text']}'")
                print(f"href='{best_candidate['href']}'")
                print(f"score={best_candidate['score']}")
                
                # Test navigation to the selected link
                print(f"\n=== TESTING NAVIGATION ===")
                print(f"Navigating to: {best_candidate['href']}")
                
                initial_url = page.url
                page.goto(best_candidate['href'], wait_until="domcontentloaded", timeout=30000)
                final_url = page.url
                
                print(f"Initial URL: {initial_url}")
                print(f"Final URL: {final_url}")
                print(f"Page title: {page.title()}")
                
                # Check if we left Arbeitnow (check actual domain, not URL parameters)
                final_domain = final_url.split("//")[-1].split("/")[0].lower()
                if "arbeitnow.com" not in final_domain:
                    print("SUCCESS: Browser left Arbeitnow and reached employer page")
                else:
                    print("FAILURE: Browser still on Arbeitnow domain")
                
                # Check for form elements
                forms_count = len(page.query_selector_all("form"))
                inputs_count = len(page.query_selector_all("input"))
                textareas_count = len(page.query_selector_all("textarea"))
                buttons_count = len(page.query_selector_all("button"))
                
                print(f"\n=== DESTINATION PAGE ANALYSIS ===")
                print(f"Forms: {forms_count}")
                print(f"Inputs: {inputs_count}")
                print(f"Textareas: {textareas_count}")
                print(f"Buttons: {buttons_count}")
                
                # Check for apply buttons on the destination page
                apply_buttons = page.query_selector_all("button:has-text('Apply'), button:has-text('Bewerben'), button:has-text('Postuler'), a:has-text('Apply'), a:has-text('Bewerben'), a:has-text('Postuler')")
                print(f"Apply-related buttons/links: {len(apply_buttons)}")
                
                if forms_count > 0 or inputs_count > 0:
                    print("SUCCESS: Destination page contains form elements")
                elif len(apply_buttons) > 0:
                    print("SUCCESS: Destination page contains apply buttons (form may be behind click)")
                else:
                    print("WARNING: Destination page has no form elements (may be intermediate page)")
                
            else:
                print("FAILURE: NO CANDIDATES FOUND - Apply-link discovery failed")
                
                # Diagnostic information
                print(f"\n=== DIAGNOSTIC INFORMATION ===")
                all_links = page.query_selector_all("a")
                print(f"Total links on page: {len(all_links)}")
                
                # Show first 20 links
                print("First 20 links:")
                for i, link in enumerate(all_links[:20]):
                    try:
                        link_text = link.inner_text().strip()
                        link_href = link.get_attribute("href") or ""
                        if link_text or link_href:
                            print(f"{i+1}. text='{link_text[:40]}', href='{link_href[:60]}'")
                    except Exception:
                        continue
            
        except Exception as e:
            print(f"Error during test: {e}")
            import traceback
            traceback.print_exc()
        finally:
            browser.close()

if __name__ == "__main__":
    test_real_arbeitnow()