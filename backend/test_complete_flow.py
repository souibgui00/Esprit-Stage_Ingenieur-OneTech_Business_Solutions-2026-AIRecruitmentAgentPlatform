"""
Real browser test for the complete application flow including intermediate Apply navigation.
Tests: Arbeitnow → Personio → Intermediate Apply → Actual Application Form
"""
import os
import sys
from playwright.sync_api import sync_playwright

def test_complete_flow():
    """Test the complete application flow with intermediate Apply navigation."""
    url = "https://www.arbeitnow.com/jobs/companies/autarcenergy/internship-go-to-market-engineering-ai-automation-berlin-236643"
    
    print(f"Testing complete flow from: {url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 2200},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            # Step 1: Navigate to Arbeitnow page
            print(f"\n=== STEP 1: Navigate to Arbeitnow ===")
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            print(f"Arbeitnow page loaded: {page.title()}")
            print(f"Current URL: {page.url}")
            
            # Step 2: Find and click first-level Apply link
            print(f"\n=== STEP 2: Find first-level Apply link ===")
            
            def score_apply_link(element, current_url):
                """Score an apply link based on relevance and priority."""
                try:
                    href = element.get_attribute("href") or ""
                    text = element.inner_text().strip().lower()
                    current_domain = current_url.split("//")[-1].split("/")[0].lower()
                    
                    if not href.startswith("http"):
                        return -1000
                    
                    link_domain = href.split("//")[-1].split("/")[0].lower()
                    link_path = href.split("//")[-1].lower() if "//" in href else href.lower()
                    score = 0
                    
                    exact_apply_patterns = [
                        "apply for this position", "apply for this job", "apply now",
                        "apply on company website", "go to application",
                        "postuler à cette offre", "candidature",
                        "bewerben", "bewerbung", "jetzt bewerben"
                    ]
                    
                    for pattern in exact_apply_patterns:
                        if pattern in text:
                            score += 12
                            break
                    
                    url_apply_patterns = ["/apply", "/application", "/career", "/careers", "/jobs", "/job"]
                    for pattern in url_apply_patterns:
                        if pattern in link_path:
                            score += 5
                            break
                    
                    known_ats_domains = ["greenhouse.io", "lever.co", "ashbyhq.com", "personio.de", "jobs.personio.de"]
                    for ats_domain in known_ats_domains:
                        if ats_domain in link_domain:
                            score += 8
                            break
                    
                    if link_domain != current_domain:
                        current_base = current_domain.split(".")[-2:] if "." in current_domain else [current_domain]
                        link_base = link_domain.split(".")[-2:] if "." in link_domain else [link_domain]
                        if current_base != link_base:
                            score += 7
                    
                    if "apply" in text and score == 0:
                        score += 2
                    
                    job_board_domains = ["arbeitnow.com", "remotive.com"]
                    if any(board in current_domain for board in job_board_domains):
                        if "/apply" in link_path and link_domain == current_domain:
                            score += 6
                    
                    return score
                except Exception:
                    return -1000
            
            apply_selectors = [
                "a:has-text('Apply')", "button:has-text('Apply')",
                "a:has-text('Apply Now')", "button:has-text('Apply Now')",
                "a.grow", "a[href*='/apply']"
            ]
            
            candidates = []
            seen_elements = set()
            
            for sel in apply_selectors:
                try:
                    elements = page.query_selector_all(sel)
                    for el in elements:
                        el_id = id(el)
                        if el_id in seen_elements:
                            continue
                        seen_elements.add(el_id)
                        
                        if el.is_visible():
                            href = el.get_attribute("href") or ""
                            text = el.inner_text().strip()
                            score = score_apply_link(el, url)
                            
                            if score > 0:
                                candidates.append({
                                    "element": el,
                                    "href": href,
                                    "text": text,
                                    "score": score
                                })
                except Exception:
                    continue
            
            candidates.sort(key=lambda x: x["score"], reverse=True)
            
            print(f"First-level candidates found: {len(candidates)}")
            for i, candidate in enumerate(candidates[:3]):
                print(f"{i+1}. text='{candidate['text'][:40]}', score={candidate['score']}")
            
            if not candidates:
                print("FAILED: No first-level apply candidates found")
                return
            
            best_candidate = candidates[0]
            print(f"Selected: text='{best_candidate['text']}', href='{best_candidate['href'][:60]}', score={best_candidate['score']}")
            
            # Step 3: Navigate to first-level destination
            print(f"\n=== STEP 3: Navigate to first-level destination ===")
            page.goto(best_candidate['href'], wait_until="domcontentloaded", timeout=30000)
            print(f"Destination page: {page.title()}")
            print(f"Destination URL: {page.url}")
            
            # Check if we left Arbeitnow
            final_domain = page.url.split("//")[-1].split("/")[0].lower()
            if "arbeitnow.com" not in final_domain:
                print("SUCCESS: Left Arbeitnow and reached employer page")
            else:
                print("FAILED: Still on Arbeitnow domain")
                return
            
            # Step 4: Check for intermediate Apply button
            print(f"\n=== STEP 4: Check for intermediate Apply button ===")
            
            current_forms = len(page.query_selector_all("form"))
            current_inputs = len(page.query_selector_all("input"))
            print(f"Current form elements: forms={current_forms}, inputs={current_inputs}")
            
            if current_forms == 0 and current_inputs == 0:
                print("No form elements found - checking for intermediate Apply button...")
                
                def find_intermediate_apply_button(page):
                    """Find intermediate Apply buttons."""
                    try:
                        candidates = []
                        
                        apply_patterns = [
                            {"text": "apply for this position", "score": 15},
                            {"text": "apply for this job", "score": 15},
                            {"text": "start application", "score": 14},
                            {"text": "start your application", "score": 14},
                            {"text": "continue to application", "score": 13},
                            {"text": "apply now", "score": 12},
                            {"text": "apply", "score": 10},
                            {"text": "bewerben", "score": 12},
                            {"text": "jetzt bewerben", "score": 14},
                            {"text": "bewerbung starten", "score": 13},
                            {"text": "postuler", "score": 12},
                            {"text": "candidature", "score": 10},
                            {"text": "déposer sa candidature", "score": 13},
                        ]
                        
                        negative_patterns = [
                            "login", "sign in", "sign up", "share", "save", "subscribe",
                            "newsletter", "similar jobs", "recommended jobs", "search jobs",
                            "view company", "back to jobs", "job-copilot", "referral"
                        ]
                        
                        selectors = [
                            "button", "a[role='button']", "[role='button']",
                            "a:has-text('Apply')", "button:has-text('Apply')",
                            "a:has-text('Bewerben')", "button:has-text('Bewerben')",
                            "a:has-text('Postuler')", "button:has-text('Postuler')",
                            ".btn-apply", "[data-testid*='apply']"
                        ]
                        
                        seen_elements = set()
                        
                        for sel in selectors:
                            try:
                                elements = page.query_selector_all(sel)
                                for el in elements:
                                    el_id = id(el)
                                    if el_id in seen_elements:
                                        continue
                                    seen_elements.add(el_id)
                                    
                                    if el.is_visible():
                                        text = el.inner_text().strip().lower()
                                        href = el.get_attribute("href") or ""
                                        
                                        if not text:
                                            continue
                                        
                                        has_negative = any(neg in text for neg in negative_patterns)
                                        if has_negative:
                                            continue
                                        
                                        score = 0
                                        for pattern in apply_patterns:
                                            if pattern["text"] in text:
                                                score = pattern["score"]
                                                break
                                        
                                        if score > 0:
                                            candidates.append({
                                                "element": el,
                                                "text": text,
                                                "href": href,
                                                "score": score
                                            })
                            except Exception:
                                continue
                        
                        candidates.sort(key=lambda x: x["score"], reverse=True)
                        return candidates
                    except Exception as e:
                        print(f"Error finding intermediate apply button: {e}")
                        return []
                
                intermediate_candidates = find_intermediate_apply_button(page)
                
                print(f"Intermediate Apply candidates found: {len(intermediate_candidates)}")
                for i, candidate in enumerate(intermediate_candidates[:3]):
                    print(f"{i+1}. text='{candidate['text'][:40]}', score={candidate['score']}")
                
                if not intermediate_candidates:
                    print("FAILED: No intermediate Apply button found")
                    return
                
                best_intermediate = intermediate_candidates[0]
                print(f"Selected intermediate: text='{best_intermediate['text']}', score={best_intermediate['score']}")
                
                # Step 5: Click intermediate Apply button
                print(f"\n=== STEP 5: Click intermediate Apply button ===")
                print(f"URL before click: {page.url}")
                print(f"Page title before click: {page.title()}")
                
                if best_intermediate["href"] and best_intermediate["href"].startswith("http"):
                    print(f"Clicking intermediate link: {best_intermediate['href']}")
                    page.goto(best_intermediate["href"], wait_until="domcontentloaded", timeout=30000)
                else:
                    print("Clicking intermediate button (SPA transition)...")
                    best_intermediate["element"].click()
                
                # Wait for dynamic content
                import time
                time.sleep(3)
                
                print(f"URL after click: {page.url}")
                print(f"Page title after click: {page.title()}")
                
                # Step 6: Verify form elements appeared
                print(f"\n=== STEP 6: Verify application form appeared ===")
                forms_after = len(page.query_selector_all("form"))
                inputs_after = len(page.query_selector_all("input"))
                textareas_after = len(page.query_selector_all("textarea"))
                selects_after = len(page.query_selector_all("select"))
                buttons_after = len(page.query_selector_all("button"))
                
                print(f"Form elements after click: forms={forms_after}, inputs={inputs_after}, textareas={textareas_after}, selects={selects_after}, buttons={buttons_after}")
                
                if forms_after > 0 or inputs_after > 0:
                    print("SUCCESS: Application form detected after intermediate Apply click")
                    
                    # Analyze form fields
                    print(f"\n=== FORM ANALYSIS ===")
                    if inputs_after > 0:
                        inputs = page.query_selector_all("input")
                        print(f"Input fields detected: {inputs_after}")
                        for i, inp in enumerate(inputs[:5]):
                            try:
                                inp_type = inp.get_attribute("type") or "text"
                                inp_name = inp.get_attribute("name") or "unknown"
                                inp_placeholder = inp.get_attribute("placeholder") or ""
                                print(f"{i+1}. type={inp_type}, name={inp_name}, placeholder={inp_placeholder[:30]}")
                            except:
                                print(f"{i+1}. (error reading input)")
                    
                    if textareas_after > 0:
                        print(f"Textarea fields detected: {textareas_after}")
                    
                    if selects_after > 0:
                        print(f"Select fields detected: {selects_after}")
                    
                    print("\n=== COMPLETE FLOW SUCCESS ===")
                    print("Arbeitnow -> Apply Now -> Personio -> Intermediate Apply -> Application Form")
                    return True
                else:
                    print("FAILED: Intermediate Apply clicked but no form elements appeared")
                    return False
            else:
                print(f"Form elements already present - skipping intermediate apply check")
                print("SUCCESS: Form already available on first-level destination")
                return True
                
        except Exception as e:
            print(f"ERROR during test: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            browser.close()

if __name__ == "__main__":
    success = test_complete_flow()
    sys.exit(0 if success else 1)