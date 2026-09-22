import os
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from groq import Groq
from playwright.sync_api import sync_playwright

from applications.ports.application_channel import IApplicationChannel
from applications.agents.greenhouse import GreenhouseAgent
from applications.agents.lever import LeverAgent
from applications.agents.ashby import AshbyAgent
from applications.agents.gem import GemAgent
from applications.agents.generic import GenericAgent

logger = logging.getLogger(__name__)


class PlaywrightApplicationChannel(IApplicationChannel):
    """
    Adapter implementing autonomous web applications using Playwright headless browser
    and specialized platform agents (Greenhouse, Lever, Generic).
    """

    def __init__(self):
        self.groq_api_key = os.environ.get("GROQ_API_KEY", "")
        self.groq_model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
        self.groq_client = Groq(api_key=self.groq_api_key) if self.groq_api_key else None
        # Register specialized platform agents (ordered by priority)
        self.agents = [
            GreenhouseAgent(),
            LeverAgent(),
            GemAgent(),
            AshbyAgent(),
            GenericAgent()  # Generic fallback must be last
        ]

    def _generate_cover_letter(self, candidate_name: str, job_title: str, company: str, match_summary: str) -> str:
        """Generates a professional, personalized cover letter using Groq LLM."""
        if not self.groq_client:
            return f"""Madame, Monsieur,

Je souhaite poser ma candidature pour le poste de {job_title} chez {company}.
Fort de mon parcours, je serais ravi d'apporter mes compétences à votre équipe.

Cordialement,
{candidate_name}"""

        prompt = f"""Rédige une lettre de motivation professionnelle, courtoise et percutante en français (max 200 mots) pour poser ma candidature au poste ci-dessous.

Candidat : {candidate_name}
Poste : {job_title}
Entreprise : {company}
Synthèse de compatibilité : {match_summary}

Ne mets pas d'en-tête de date ni d'adresse. Commence par 'Madame, Monsieur,' et termine par la signature du candidat."""

        try:
            response = self.groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Tu es un assistant RH spécialisé dans la rédaction de lettres de motivation percutantes."},
                    {"role": "user", "content": prompt}
                ],
                model=self.groq_model,
                temperature=0.6,
                max_tokens=400,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"Error generating cover letter via Groq: {e}")
            return f"""Madame, Monsieur,

Je postule avec enthousiasme au poste de {job_title} chez {company}.
{match_summary}

Cordialement,
{candidate_name}"""

    def _is_active_captcha_present(self, page) -> bool:
        """
        Check if a visible, blocking CAPTCHA challenge is actively displayed on the page.
        Avoids false positives from passive scripts (e.g. Turnstile scripts or hidden tokens).
        """
        try:
            # Check for Cloudflare challenge screen / page blocking
            title = page.title().lower()
            if "just a moment" in title or "attention required" in title or "cloudflare" in title:
                return True

            challenge_selectors = [
                "iframe[src*='recaptcha']:not([aria-hidden='true'])",
                "iframe[src*='hcaptcha']:not([aria-hidden='true'])",
                "iframe[src*='challenges.cloudflare.com']:not([aria-hidden='true'])",
                "iframe[title*='recaptcha' i]:not([aria-hidden='true'])",
                "iframe[title*='challenge' i]:not([aria-hidden='true'])",
                "#cf-challenge-running",
                "#challenge-form",
                "#challenge-stage",
                ".g-recaptcha[data-sitekey]",
                ".h-captcha[data-sitekey]"
            ]
            for sel in challenge_selectors:
                try:
                    elements = page.query_selector_all(sel)
                    for el in elements:
                        if el.is_visible():
                            box = el.bounding_box()
                            if box and box.get("width", 0) >= 100 and box.get("height", 0) >= 40:
                                return True
                except Exception:
                    pass
        except Exception:
            pass
        return False

    def submit(
        self,
        application,
        cv,
        job_offer,
        candidate_email: Optional[str] = None,
        match=None,
        personal_info=None,
        experiences=None,
        skills=None,
        user_responses: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        logs: List[Dict[str, Any]] = []
        screenshots: Dict[str, str] = {}
        
        def add_log(step: str, message: str, status: str = "INFO"):
            entry = {
                "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
                "step": step,
                "message": message,
                "status": status
            }
            logs.append(entry)
            logger.info(f"[{step}] {message}")

        def take_resilient_screenshot(page, abs_path: str, rel_path: str, label: str = "screenshot") -> bool:
            """
            Take a screenshot with timeout protection and fallback logic.
            Returns True if successful, False otherwise.
            """
            try:
                # Try full_page screenshot first with 60s timeout
                page.screenshot(path=abs_path, full_page=True, timeout=60000)
                screenshots[label] = rel_path
                return True
            except Exception as e:
                add_log("SCREENSHOT", f"Full-page screenshot failed for {label}: {str(e)[:100]}", "WARNING")
                try:
                    # Fallback to non-full-page screenshot
                    page.screenshot(path=abs_path, timeout=60000)
                    screenshots[label] = rel_path
                    add_log("SCREENSHOT", f"Non-full-page screenshot succeeded for {label}", "SUCCESS")
                    return True
                except Exception as e2:
                    add_log("SCREENSHOT", f"Screenshot completely failed for {label}: {str(e2)[:100]}", "WARNING")
                    return False

        candidate_name = personal_info.full_name if personal_info and personal_info.full_name else "Candidat"
        email_to_use = candidate_email or (personal_info.email if personal_info else "candidat@example.com")

        # 1. Generate Cover Letter
        add_log("1_COVER_LETTER", "Génération de la lettre de motivation personnalisée via Groq LLM...")
        summary_text = match.summary if match and match.summary else "Profil compatible avec le poste."
        cover_letter = self._generate_cover_letter(candidate_name, job_offer.title, job_offer.company, summary_text)
        add_log("1_COVER_LETTER", "Lettre de motivation générée avec succès.", "SUCCESS")

        # Create screenshot output dir
        app_id_str = str(application.id)
        rel_dir = f"screenshots/applications/{app_id_str}"
        abs_dir = os.path.join("/app/static", rel_dir)
        os.makedirs(abs_dir, exist_ok=True)

        url = job_offer.source_url
        if not url:
            add_log("2_NAVIGATION", "Aucune URL source disponible pour cette offre.", "ERROR")
            return {
                "success": False,
                "error_message": "Aucune URL source pour cette offre d'emploi.",
                "cover_letter": cover_letter,
                "execution_logs": logs,
                "screenshots": screenshots
            }

        add_log("2_NAVIGATION", f"Lancement du navigateur Playwright (Chromium headless) vers {url}...")

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
                )
                context = browser.new_context(
                    viewport={"width": 1280, "height": 2200},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                
                # Set default timeout to 60 seconds for all operations
                page.set_default_timeout(60000)
                
                # Apply stealth to bypass bot detection
                try:
                    from playwright_stealth import Stealth
                    stealth_obj = Stealth()
                    stealth_obj.apply_stealth_sync(page)
                    add_log("2_NAVIGATION", "Mode Stealth activé avec succès.", "SUCCESS")
                except Exception as stealth_err:
                    add_log("2_NAVIGATION", f"Stealth non disponible: {str(stealth_err)}", "WARNING")

                # Open page
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(2)
                except Exception as goto_err:
                    add_log("2_NAVIGATION", f"Chargement partiel de la page: {str(goto_err)}", "WARNING")

                # Screenshot 1: Page opened
                img1_rel = f"/static/{rel_dir}/step1_opened.png"
                img1_abs = os.path.join(abs_dir, "step1_opened.png")
                take_resilient_screenshot(page, img1_abs, img1_rel, "step1_opened")
                page_title = page.title()
                add_log("2_NAVIGATION", f"Page d'origine ouverte : '{page_title}'. Capture d'écran enregistrée.", "SUCCESS")

                # --- NEW TAB & EXTERNAL REDIRECTION HANDLING ---
                add_log("3_REDIRECT_HANDLING", "Recherche des liens de candidature avec système de priorité...")
                
                # Collect all candidate apply links and score them
                def score_apply_link(element, current_url):
                    """Score an apply link based on relevance and priority."""
                    try:
                        tag_name = element.evaluate("el => el.tagName.toLowerCase()") or ""
                        role = element.get_attribute("role") or ""
                        href = element.get_attribute("href") or ""
                        text = element.inner_text().strip().lower()
                        current_domain = current_url.split("//")[-1].split("/")[0].lower()
                        
                        # Check if we're on a LinkedIn job page
                        is_linkedin_job_page = "linkedin.com/jobs" in current_url.lower()
                        
                        is_button = tag_name == "button" or role == "button" or not href

                        # If it's not a button and has an invalid/anchor href
                        if not is_button and not href.startswith("http") and not href.startswith("/"):
                            return -1000  # Invalid link
                        
                        link_domain = href.split("//")[-1].split("/")[0].lower() if href.startswith("http") else current_domain
                        link_path = href.split("//")[-1].lower() if "//" in href else href.lower()
                        score = 0
                        
                        # LinkedIn-specific logic for job pages
                        if is_linkedin_job_page:
                            # Strongly penalize links to other job pages (near absolute rejection)
                            if "/jobs/view/" in link_path or "/jobs/search/" in link_path or "/jobs/collections/" in link_path:
                                return -9999
                            
                            # Penalize job listing/similar jobs links
                            negative_linkedin_patterns = [
                                "see more jobs", "similar jobs", "web developer jobs",
                                "software engineer jobs", "jobs you may like",
                                "recommended jobs", "more jobs like this", "dismiss",
                                "save", "save job", "share"
                            ]
                            if any(pattern in text for pattern in negative_linkedin_patterns):
                                return -5000
                            
                            # Prefer elements in main job header (not sidebar or recommendations)
                            is_in_header = False
                            try:
                                is_in_header = element.evaluate("""el => {
                                    const header = el.closest('.jobs-unified-top-card, .jobs-details-top-card, .top-card, header, [data-test-id="jobs-details-apply-button"], .jobs-apply-button');
                                    return header !== null;
                                }""")
                            except Exception:
                                pass
                            
                            # Give very high priority to real apply buttons for the current job
                            linkedin_apply_patterns = [
                                "easy apply",
                                "apply on company website",
                                "apply on company site",
                                "apply now",
                                "apply"
                            ]
                            for pattern in linkedin_apply_patterns:
                                if pattern in text:
                                    if "easy apply" in pattern:
                                        score += 35
                                    elif "company" in pattern:
                                        score += 30
                                    else:
                                        score += 20
                                    break
                            
                            if is_in_header:
                                score += 15
                            
                            if is_button:
                                score += 5
                            
                            return score if score > 0 else -500
                        
                        # Non-LinkedIn scoring
                        # Negative scoring first: Reject known promotional/newsletter/service links
                        promotional_patterns = [
                            "job-copilot",
                            "referral",
                            "share",
                            "newsletter",
                            "subscribe",
                            "similar jobs",
                            "privacy policy",
                            "terms of service",
                            "cookie"
                        ]
                        for pattern in promotional_patterns:
                            if pattern in href.lower() or pattern in text:
                                return -1000
                        
                        # Priority 1: Exact application text (highest priority: +12 to +25)
                        exact_apply_patterns = [
                            "apply on company site",  # The Muse specific - highest priority
                            "apply on company website",
                            "apply externally",
                            "apply for this position",
                            "apply for this job", 
                            "apply now",
                            "go to application",
                            "postuler à cette offre",
                            "candidature",
                            "bewerben",
                            "bewerbung",
                            "jetzt bewerben",
                            "apply to this job"
                        ]
                        
                        for pattern in exact_apply_patterns:
                            if pattern in text:
                                if "company" in pattern or "external" in pattern:
                                    score += 25
                                else:
                                    score += 15
                                break
                        
                        # Priority 2: URL patterns indicating application pages (+3 to +8)
                        url_apply_patterns = [
                            "/apply",
                            "/application",
                            "/career",
                            "/careers",
                            "/jobs",
                            "/job",
                            "/vacancy",
                            "/position",
                            ".jobs.personio.de",
                            ".greenhouse.io",
                            ".lever.co",
                            ".ashbyhq.com",
                            ".workable.com",
                            ".myworkdayjobs.com"
                        ]
                        
                        for pattern in url_apply_patterns:
                            if pattern in link_path:
                                score += 6
                                break
                        
                        # Priority 3: Known ATS domains (+10)
                        known_ats_domains = [
                            "greenhouse.io", "lever.co", "ashbyhq.com", "ashby", 
                            "workable.com", "workable", "myworkdayjobs.com", "smartrecruiters.com",
                            "personio.de", "jobs.personio.de"
                        ]
                        for ats_domain in known_ats_domains:
                            if ats_domain in link_domain:
                                score += 10
                                break
                        
                        # Priority 4: External domain to job board (+8)
                        if href.startswith("http") and link_domain != current_domain:
                            current_base = current_domain.split(".")[-2:] if "." in current_domain else [current_domain]
                            link_base = link_domain.split(".")[-2:] if "." in link_domain else [link_domain]
                            if current_base != link_base:
                                score += 8
                        
                        # Priority 5: Generic "Apply" text
                        if "apply" in text and score == 0:
                            score += 5
                        elif any(w in text for w in ["postuler", "bewerben"]):
                            score += 5
                        
                        # Priority 6: Interactive button boost
                        if is_button:
                            score += 3
                        
                        # Special case: Job board intermediate apply pages
                        job_board_domains = ["arbeitnow.com", "remotive.com", "wellfound.com", "angellist.co"]
                        if any(board in current_domain for board in job_board_domains):
                            if "/apply" in link_path:
                                score += 8
                        
                        return score
                    except Exception:
                        return -1000
                
                # Find all candidate apply links using various selectors
                apply_selectors = [
                    # LinkedIn specific - highest priority for LinkedIn pages
                    "button:has-text('Easy Apply')", "a:has-text('Easy Apply')",
                    
                    # The Muse specific - highest priority
                    "a:has-text('Apply on company site')", "button:has-text('Apply on company site')",
                    "a:has-text('Apply on company website')", "button:has-text('Apply on company website')",
                    "a:has-text('Apply externally')", "button:has-text('Apply externally')",
                    
                    # English apply patterns
                    "a:has-text('Apply')", "button:has-text('Apply')",
                    "a:has-text('Apply Now')", "button:has-text('Apply Now')",
                    "a:has-text('Apply for this job')", "a:has-text('Apply for this position')",
                    "a:has-text('Go to application')",
                    
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
                    except Exception:
                        continue
                
                # Sort candidates by score (highest first)
                candidates.sort(key=lambda x: x["score"], reverse=True)
                
                add_log("3_REDIRECT_HANDLING", f"Candidats trouvés : {len(candidates)}", "INFO")
                
                for i, candidate in enumerate(candidates):
                    add_log("3_REDIRECT_HANDLING", 
                           f"Candidat {i+1}: text='{candidate['text'][:50]}', href='{candidate['href'][:80]}', score={candidate['score']}", 
                           "INFO")
                
                # Select best candidate
                apply_element = None
                selected_href = None
                
                if candidates:
                    best_candidate = candidates[0]
                    apply_element = best_candidate["element"]
                    selected_href = best_candidate["href"]
                    add_log("3_REDIRECT_HANDLING", 
                           f"Lien sélectionné : text='{best_candidate['text'][:50]}', href='{best_candidate['href'][:80]}', score={best_candidate['score']}", 
                           "SUCCESS")
                    
                    # LinkedIn-specific check: if selected Easy Apply, check if login is required
                    if "linkedin.com/jobs" in url.lower() and "easy apply" in best_candidate['text'].lower():
                        add_log("3_REDIRECT_HANDLING", "LinkedIn Easy Apply détecté. Vérification si connexion requise...", "INFO")
                        try:
                            # Click the Easy Apply button to check if it triggers login
                            try:
                                apply_element.click(timeout=5000)
                                time.sleep(2)
                                
                                # Check if we're redirected to login page
                                current_url = page.url.lower()
                                if "login" in current_url or "auth" in current_url or "signin" in current_url:
                                    add_log("3_REDIRECT_HANDLING", "LinkedIn Easy Apply requires login. ACTION_REQUIRED.", "WARNING")
                                    browser.close()
                                    return {
                                        "success": True,
                                        "status": "ACTION_REQUIRED",
                                        "error_message": "LinkedIn Easy Apply requires being logged in. Please log in to LinkedIn and try again.",
                                        "pending_questions": [],
                                        "cover_letter": cover_letter,
                                        "execution_logs": logs,
                                        "screenshots": screenshots
                                    }
                            except Exception as click_err:
                                add_log("3_REDIRECT_HANDLING", f"Erreur lors du clic Easy Apply : {str(click_err)[:80]}", "WARNING")
                        except Exception as easy_apply_err:
                            add_log("3_REDIRECT_HANDLING", f"Erreur vérification Easy Apply : {str(easy_apply_err)[:80]}", "WARNING")
                else:
                    add_log("3_REDIRECT_HANDLING", "Aucun lien de candidature valide trouvé.", "WARNING")
                    
                    # Zero-candidate diagnostics
                    add_log("3_REDIRECT_HANDLING", "=== DIAGNOSTIC: No application candidates detected ===", "INFO")
                    add_log("3_REDIRECT_HANDLING", f"Current URL: {page.url}", "INFO")
                    add_log("3_REDIRECT_HANDLING", f"Current page title: {page.title()}", "INFO")
                    
                    # Count visible elements
                    all_links = page.query_selector_all("a")
                    all_buttons = page.query_selector_all("button")
                    add_log("3_REDIRECT_HANDLING", f"Number of visible links: {len(all_links)}", "INFO")
                    add_log("3_REDIRECT_HANDLING", f"Number of visible buttons: {len(all_buttons)}", "INFO")
                    
                    # Log first 15-20 useful visible links
                    add_log("3_REDIRECT_HANDLING", "Visible links inspected (first 20):", "INFO")
                    for i, link in enumerate(all_links[:20]):
                        try:
                            link_text = link.inner_text().strip()
                            link_href = link.get_attribute("href") or ""
                            if link_text or link_href:  # Only log if it has content
                                add_log("3_REDIRECT_HANDLING", 
                                       f"{i+1}. text='{link_text[:40]}', href='{link_href[:60]}'", 
                                       "INFO")
                        except Exception:
                            continue

                if apply_element:
                    # Navigate to the selected application link or click button
                    if selected_href and selected_href.startswith("http"):
                        add_log("3_REDIRECT_HANDLING", f"Navigation vers : {selected_href}", "INFO")
                        page.goto(selected_href, wait_until="domcontentloaded", timeout=30000)
                        time.sleep(3)
                        
                        # Take screenshot of destination page (separate from original)
                        img1_redirect_rel = f"/static/{rel_dir}/step1_after_redirect.png"
                        img1_redirect_abs = os.path.join(abs_dir, "step1_after_redirect.png")
                        take_resilient_screenshot(page, img1_redirect_abs, img1_redirect_rel, "step1_after_redirect")
                        
                        destination_title = page.title()
                        destination_url = page.url
                        add_log("3_REDIRECT_HANDLING", f"Destination atteinte : '{destination_title}'", "SUCCESS")
                        add_log("3_REDIRECT_HANDLING", f"URL finale : {destination_url}", "INFO")
                        
                        # Validate destination page
                        add_log("3_REDIRECT_HANDLING", "Validation de la page de destination...", "INFO")
                        forms_count = page.query_selector_all("form").length if hasattr(page.query_selector_all("form"), "length") else len(page.query_selector_all("form"))
                        inputs_count = page.query_selector_all("input").length if hasattr(page.query_selector_all("input"), "length") else len(page.query_selector_all("input"))
                        textareas_count = page.query_selector_all("textarea").length if hasattr(page.query_selector_all("textarea"), "length") else len(page.query_selector_all("textarea"))
                        selects_count = page.query_selector_all("select").length if hasattr(page.query_selector_all("select"), "length") else len(page.query_selector_all("select"))
                        buttons_count = page.query_selector_all("button").length if hasattr(page.query_selector_all("button"), "length") else len(page.query_selector_all("button"))
                        
                        add_log("3_REDIRECT_HANDLING", 
                               f"Validation destination : forms={forms_count}, inputs={inputs_count}, textareas={textareas_count}, selects={selects_count}, buttons={buttons_count}", 
                               "INFO")
                        
                        # If destination has no form elements, log warning but continue
                        if forms_count == 0 and inputs_count == 0 and textareas_count == 0:
                            add_log("3_REDIRECT_HANDLING", "Attention : La page de destination ne semble pas contenir de formulaire. Il peut s'agir d'une page intermédiaire de l'employeur.", "WARNING")
                    else:
                        # Attempt to click it and catch new tab if it opens
                        add_log("3_REDIRECT_HANDLING", "Clic sur le bouton d'application dynamique (attente nouvel onglet)...", "INFO")
                        try:
                            with context.expect_page(timeout=10000) as new_page_info:
                                apply_element.click()
                            
                            # Switch context to the new page/tab
                            new_page = new_page_info.value
                            new_page.wait_for_load_state("domcontentloaded")
                            time.sleep(3)
                            
                            # Apply stealth on new page
                            try:
                                from playwright_stealth import stealth
                                stealth(new_page)
                            except Exception:
                                pass

                            # Switch main page pointer
                            page = new_page
                            
                            # Take screenshot of destination page
                            img1_redirect_rel = f"/static/{rel_dir}/step1_after_redirect.png"
                            img1_redirect_abs = os.path.join(abs_dir, "step1_after_redirect.png")
                            take_resilient_screenshot(page, img1_redirect_abs, img1_redirect_rel, "step1_after_redirect")
                            
                            destination_title = page.title()
                            destination_url = page.url
                            add_log("3_REDIRECT_HANDLING", f"Nouvel onglet détecté et activé : '{destination_title}'", "SUCCESS")
                            add_log("3_REDIRECT_HANDLING", f"URL finale : {destination_url}", "INFO")
                            
                            # Validate destination page
                            forms_count = page.query_selector_all("form").length if hasattr(page.query_selector_all("form"), "length") else len(page.query_selector_all("form"))
                            inputs_count = page.query_selector_all("input").length if hasattr(page.query_selector_all("input"), "length") else len(page.query_selector_all("input"))
                            textareas_count = page.query_selector_all("textarea").length if hasattr(page.query_selector_all("textarea"), "length") else len(page.query_selector_all("textarea"))
                            
                            add_log("3_REDIRECT_HANDLING", 
                                   f"Validation destination : forms={forms_count}, inputs={inputs_count}, textareas={textareas_count}", 
                                   "INFO")
                            
                        except Exception as click_err:
                            add_log("3_REDIRECT_HANDLING", f"Pas de redirection d'onglet détectée ou erreur : {str(click_err)}. Poursuite sur la page actuelle.", "INFO")
                else:
                    add_log("3_REDIRECT_HANDLING", "Aucun lien de candidature valide trouvé. Recherche directe du formulaire sur la page actuelle.", "INFO")

                # --- INTERMEDIATE APPLY NAVIGATION ---
                # Check if we need to click an intermediate Apply button on the destination page
                add_log("4_INTERMEDIATE_APPLY", "Checking for intermediate Apply button on destination page...", "INFO")
                
                def find_intermediate_apply_button(page):
                    """Find and score intermediate Apply buttons on the page."""
                    try:
                        candidates = []
                        
                        # Define apply button patterns with scoring
                        apply_patterns = [
                            # English - High priority
                            {"text": "apply for this position", "score": 15},
                            {"text": "apply for this job", "score": 15},
                            {"text": "start application", "score": 14},
                            {"text": "start your application", "score": 14},
                            {"text": "continue to application", "score": 13},
                            {"text": "apply now", "score": 12},
                            {"text": "apply", "score": 10},
                            
                            # German - High priority
                            {"text": "bewerben", "score": 12},
                            {"text": "jetzt bewerben", "score": 14},
                            {"text": "bewerbung starten", "score": 13},
                            
                            # French - High priority
                            {"text": "postuler", "score": 12},
                            {"text": "candidature", "score": 10},
                            {"text": "déposer sa candidature", "score": 13},
                        ]
                        
                        # Define negative patterns (things to reject)
                        negative_patterns = [
                            "login", "sign in", "sign up", "share", "save", "subscribe",
                            "newsletter", "similar jobs", "recommended jobs", "search jobs",
                            "view company", "back to jobs", "job-copilot", "referral"
                        ]
                        
                        # Search for buttons and links
                        selectors = [
                            "button", "a[role='button']", "[role='button']",
                            "a:has-text('Apply')", "button:has-text('Apply')",
                            "a:has-text('Bewerben')", "button:has-text('Bewerben')",
                            "a:has-text('Postuler')", "button:has-text('Postuler')",
                            ".btn-apply", "[data-testid*='apply']", ".apply-button"
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
                                        
                                        # Skip if no text content
                                        if not text:
                                            continue
                                        
                                        # Check for negative patterns
                                        has_negative = any(neg in text for neg in negative_patterns)
                                        if has_negative:
                                            continue
                                        
                                        # Score based on text patterns
                                        score = 0
                                        for pattern in apply_patterns:
                                            if pattern["text"] in text:
                                                score = pattern["score"]
                                                break
                                        
                                        # Additional scoring for content container preference
                                        # Prefer elements in main content areas over header/footer
                                        try:
                                            parent = el.evaluate("el => el.closest('main, article, .job-description, .application-cta')")
                                            if parent:
                                                score += 3
                                        except:
                                            pass
                                        
                                        # Prefer elements with apply-related attributes
                                        try:
                                            has_apply_attr = any(
                                                attr in (el.get_attribute(name) or "").lower() 
                                                for name in ["class", "id", "data-testid", "data-test"]
                                                for attr in ["apply", "application", "bewerben", "postuler"]
                                            )
                                            if has_apply_attr:
                                                score += 2
                                        except:
                                            pass
                                        
                                        if score > 0:
                                            candidates.append({
                                                "element": el,
                                                "text": text,
                                                "href": href,
                                                "score": score
                                            })
                            except Exception:
                                continue
                        
                        # Sort by score (highest first)
                        candidates.sort(key=lambda x: x["score"], reverse=True)
                        return candidates
                        
                    except Exception as e:
                        add_log("4_INTERMEDIATE_APPLY", f"Error finding intermediate apply button: {str(e)}", "ERROR")
                        return []
                
                # Only attempt intermediate apply if we don't already have form elements
                current_forms = len(page.query_selector_all("form"))
                current_inputs = len(page.query_selector_all("input"))
                
                if current_forms == 0 and current_inputs == 0:
                    add_log("4_INTERMEDIATE_APPLY", f"No form elements found (forms={current_forms}, inputs={current_inputs}). Checking for intermediate Apply button...", "INFO")
                    
                    intermediate_candidates = find_intermediate_apply_button(page)
                    
                    if intermediate_candidates:
                        best_candidate = intermediate_candidates[0]
                        add_log("4_INTERMEDIATE_APPLY", 
                               f"Intermediate Apply button found: text='{best_candidate['text']}', score={best_candidate['score']}", 
                               "SUCCESS")
                        
                        # Log current state before click
                        add_log("4_INTERMEDIATE_APPLY", f"Current URL before click: {page.url}", "INFO")
                        add_log("4_INTERMEDIATE_APPLY", f"Current page title: {page.title()}", "INFO")
                        
                        # Handle the click (same-page, new-tab, or SPA)
                        try:
                            if best_candidate["href"] and best_candidate["href"].startswith("http"):
                                # It's a link - navigate to it
                                add_log("4_INTERMEDIATE_APPLY", f"Clicking intermediate Apply link: {best_candidate['href']}", "INFO")
                                page.goto(best_candidate["href"], wait_until="domcontentloaded", timeout=30000)
                            else:
                                # It's a button or JavaScript link - click it
                                add_log("4_INTERMEDIATE_APPLY", "Clicking intermediate Apply button (may trigger SPA transition)...", "INFO")
                                
                                # Check if it opens a new tab
                                try:
                                    with context.expect_page(timeout=5000) as new_page_info:
                                        best_candidate["element"].click()
                                    
                                    # New tab opened - switch to it
                                    new_page = new_page_info.value
                                    new_page.wait_for_load_state("domcontentloaded")
                                    
                                    # Apply stealth to new page
                                    try:
                                        from playwright_stealth import stealth
                                        stealth(new_page)
                                    except Exception:
                                        pass
                                    
                                    # Switch main page pointer
                                    page = new_page
                                    add_log("4_INTERMEDIATE_APPLY", "New tab detected and switched to intermediate page", "INFO")
                                    
                                except Exception:
                                    # No new tab - same page or SPA transition
                                    best_candidate["element"].click()
                                    add_log("4_INTERMEDIATE_APPLY", "Same-page/SPA transition triggered", "INFO")
                            
                            # Wait for dynamic content to load
                            time.sleep(3)
                            
                            # Take screenshot after intermediate apply
                            img_intermediate_rel = f"/static/{rel_dir}/step1_after_intermediate_apply.png"
                            img_intermediate_abs = os.path.join(abs_dir, "step1_after_intermediate_apply.png")
                            take_resilient_screenshot(page, img_intermediate_abs, img_intermediate_rel, "step1_after_intermediate_apply")
                            
                            # Log state after click
                            add_log("4_INTERMEDIATE_APPLY", f"URL after click: {page.url}", "INFO")
                            add_log("4_INTERMEDIATE_APPLY", f"Page title after click: {page.title()}", "INFO")
                            
                            # Verify form elements appeared
                            forms_after = len(page.query_selector_all("form"))
                            inputs_after = len(page.query_selector_all("input"))
                            textareas_after = len(page.query_selector_all("textarea"))
                            selects_after = len(page.query_selector_all("select"))
                            buttons_after = len(page.query_selector_all("button"))
                            
                            add_log("4_INTERMEDIATE_APPLY", 
                                   f"Form elements after click: forms={forms_after}, inputs={inputs_after}, textareas={textareas_after}, selects={selects_after}, buttons={buttons_after}", 
                                   "INFO")
                            
                            # Check if we actually reached an application form
                            if forms_after > 0 or inputs_after > 0:
                                add_log("4_INTERMEDIATE_APPLY", "SUCCESS: Application form detected after intermediate Apply click", "SUCCESS")
                            else:
                                add_log("4_INTERMEDIATE_APPLY", "WARNING: Intermediate Apply clicked but no form elements appeared. May need additional user action.", "WARNING")
                                # Fall back to ACTION_REQUIRED as specified
                                browser.close()
                                return {
                                    "success": True,
                                    "status": "ACTION_REQUIRED",
                                    "error_message": "Intermediate Apply button was clicked but application form did not appear. Please complete the application manually.",
                                    "cover_letter": cover_letter,
                                    "execution_logs": logs,
                                    "screenshots": screenshots
                                }
                            
                        except Exception as click_err:
                            add_log("4_INTERMEDIATE_APPLY", f"Error clicking intermediate Apply button: {str(click_err)}", "ERROR")
                            add_log("4_INTERMEDIATE_APPLY", "Proceeding without intermediate apply click", "WARNING")
                    else:
                        add_log("4_INTERMEDIATE_APPLY", "No intermediate Apply button found. Proceeding with current page.", "INFO")
                else:
                    add_log("4_INTERMEDIATE_APPLY", f"Form elements already present (forms={current_forms}, inputs={current_inputs}). Skipping intermediate apply check.", "INFO")

                # Detect active specialized platform agent on the REAL target page
                active_agent = None
                for agent in self.agents:
                    if agent.detect(page, page.url):
                        active_agent = agent
                        break

                agent_name = active_agent.__class__.__name__
                add_log("5_AGENT_SELECTION", f"Agent de plateforme sélectionné pour le formulaire : {agent_name}", "SUCCESS")

                # Check for blocking walls (CAPTCHA or Login) before filling
                add_log("6_BLOCK_CHECK", "Analyse de la page à la recherche de CAPTCHA ou de connexion requise...")
                block_reason = active_agent.detect_blocking(page)
                if block_reason:
                    add_log("6_BLOCK_CHECK", f"Blocage détecté : {block_reason}. Tentative de résolution active avec le mode Stealth (attente 20s)...", "WARNING")
                    
                    resolved = False
                    # Wait up to 20 seconds, checking every 4 seconds
                    for i in range(5):
                        time.sleep(4)
                        # Check again
                        current_block = active_agent.detect_blocking(page)
                        # Take refreshed screenshot of the waiting state
                        img2_rel = f"/static/{rel_dir}/step2_filled.png"
                        img2_abs = os.path.join(abs_dir, "step2_filled.png")
                        take_resilient_screenshot(page, img2_abs, img2_rel, "step2_filled")

                        if not current_block:
                            add_log("6_BLOCK_CHECK", "Blocage contourné avec succès par l'agent Stealth !", "SUCCESS")
                            resolved = True
                            break
                        else:
                            add_log("6_BLOCK_CHECK", f"Toujours bloqué... essai {i+1}/5.", "INFO")
                    
                    if not resolved:
                        add_log("6_BLOCK_CHECK", f"Blocage persistant après attente. Statut mis à jour en Action Requise.", "WARNING")
                        browser.close()
                        return {
                            "success": True,
                            "status": "MANUAL_REQUIRED",
                            "error_message": f"Action humaine requise : {block_reason}. Veuillez résoudre le CAPTCHA ou vous connecter sur le site de l'offre.",
                            "cover_letter": cover_letter,
                            "execution_logs": logs,
                            "screenshots": screenshots
                        }

                add_log("6_BLOCK_CHECK", "Aucun mur de blocage actif détecté. Poursuite de la candidature.", "SUCCESS")

                # Pass screenshot context to agents for their own screenshot capture
                page._screenshots = screenshots
                page._screenshot_dir = rel_dir
                
                # Fill the form using the active agent
                fill_result = active_agent.fill_form(
                    page=page,
                    cv=cv,
                    personal_info=personal_info,
                    cover_letter=cover_letter,
                    skills=skills or [],
                    experiences=experiences or [],
                    add_log=add_log,
                    user_responses=user_responses
                )
                
                filled_success = fill_result.get("success", False)
                pending_questions = fill_result.get("pending_questions", [])

                # Screenshot 2: After form-filling attempt
                img2_rel = f"/static/{rel_dir}/step2_after_fill_attempt.png"
                img2_abs = os.path.join(abs_dir, "step2_after_fill_attempt.png")
                take_resilient_screenshot(page, img2_abs, img2_rel, "step2_after_fill_attempt")

                # Check if there are pending questions that need user input
                if pending_questions:
                    add_log("7_FILLING_FIELDS", f"Questions en attente détectées : {len(pending_questions)}. Intervention utilisateur requise.", "WARNING")
                    browser.close()
                    return {
                        "success": True,
                        "status": "ACTION_REQUIRED",
                        "error_message": "Some questions require your answers before the application can be submitted.",
                        "pending_questions": pending_questions,
                        "cover_letter": cover_letter,
                        "execution_logs": logs,
                        "screenshots": screenshots
                    }

                if not filled_success:
                    add_log("7_FILLING_FIELDS", "L'agent n'a trouvé aucun champ de formulaire modifiable. Soumission annulée par sécurité.", "WARNING")
                    browser.close()
                    return {
                        "success": True,
                        "status": "MANUAL_REQUIRED",
                        "error_message": "Champs non remplis : le formulaire n'a pas pu être analysé automatiquement. Veuillez remplir et soumettre manuellement via la lettre de motivation ci-dessous.",
                        "cover_letter": cover_letter,
                        "execution_logs": logs,
                        "screenshots": screenshots
                    }
                else:
                    add_log("7_FILLING_FIELDS", "Formulaire rempli avec succès par l'agent.", "SUCCESS")
                    # Rename screenshot to reflect successful fill
                    img2_filled_rel = f"/static/{rel_dir}/step2_filled.png"
                    img2_filled_abs = os.path.join(abs_dir, "step2_filled.png")
                    take_resilient_screenshot(page, img2_filled_abs, img2_filled_rel, "step2_filled")

                # Attempt to click submit ONLY if fields were filled
                submit_clicked = active_agent.submit_form(page, add_log)

                # Verify if submission actually succeeded (not just clicked)
                submitted = False
                error_msg = "Champs de base remplis, mais des questions spécifiques à l'offre (ex: salaire, contrat) nécessitent votre saisie manuelle pour finaliser."
                
                if submit_clicked:
                    time.sleep(4)  # Let pages load/redirect
                    
                    current_url = page.url.lower()
                    page_content = page.content().lower()

                    # 1. Negative checks: spam banners, CAPTCHAs, bot detections, validation errors
                    spam_patterns = [
                        "flagged as possible spam",
                        "marked as spam",
                        "suspected spam",
                        "blocked by spam filter",
                        "unable to submit your application at this time",
                        "unusual activity",
                        "submission failed",
                        "error submitting application"
                    ]
                    has_spam_banner = any(p in page_content for p in spam_patterns)

                    has_active_captcha = self._is_active_captcha_present(page)

                    validation_error_patterns = [
                        "please enter", "required field", "is required", "champ obligatoire",
                        "ce champ est requis", "invalid email", "field cannot be blank",
                        "select a country"
                    ]
                    has_validation_errors = any(err in page_content for err in validation_error_patterns)

                    # 2. Positive confirmation checks
                    success_urls = ["thank", "success", "confirm", "received", "complete", "submitted"]
                    success_texts = [
                        "thank you for applying", "thank you for your application",
                        "application submitted", "application received", "candidature reçue",
                        "merci pour votre candidature", "votre candidature a bien été envoyée",
                        "candidature transmise", "application has been submitted"
                    ]
                    
                    url_success = any(s in current_url for s in success_urls)
                    text_success = any(t in page_content for t in success_texts)

                    if has_spam_banner:
                        submitted = False
                        error_msg = "La candidature a été bloquée par le filtre anti-spam de la plateforme (possible spam)."
                        add_log("8_SUBMISSION", f"Alerte : Filtre anti-spam détecté ({error_msg}). Soumission non validée.", "WARNING")
                    elif has_active_captcha:
                        submitted = False
                        error_msg = "Intervention requise : Un CAPTCHA actif bloque la soumission automatique. Veuillez finaliser manuellement."
                        add_log("8_SUBMISSION", "Détection d'un CAPTCHA actif bloquant la soumission automatique.", "WARNING")
                    elif has_validation_errors:
                        submitted = False
                        error_msg = "Champs obligatoires manquants ou invalides détectés sur le formulaire après soumission."
                        add_log("8_SUBMISSION", f"Alerte : Erreurs de validation du formulaire détectées ({error_msg}).", "WARNING")
                    elif (url_success or text_success):
                        submitted = True
                        add_log("8_SUBMISSION", "Validation de soumission réussie (confirmation détectée).", "SUCCESS")
                        
                        # Screenshot: After successful submission
                        img3_rel = f"/static/{rel_dir}/step3_success.png"
                        img3_abs = os.path.join(abs_dir, "step3_success.png")
                        take_resilient_screenshot(page, img3_abs, img3_rel, "step3_success")
                    else:
                        # Check for security/verification code
                        if any(w in page_content for w in ["verification code", "security code", "verification_code", "security_code", "code de vérification", "code de sécurité", "saisir le code"]):
                            error_msg = "Intervention requise : Un code de vérification vous a été envoyé par email. Veuillez finaliser la soumission en saisissant ce code."
                            add_log("8_SUBMISSION", "Détection d'un code de vérification / sécurité requis par l'entreprise.", "WARNING")
                        
                        # Check if form inputs are still visible in any of the frames
                        try:
                            any_visible_inputs = False
                            for frame in page.frames:
                                try:
                                    inputs = frame.locator(
                                        "input[type='text'], input[type='email'], input[type='tel'], input[type='url'], input:not([type])"
                                    )
                                    count = inputs.count()
                                    for idx in range(count):
                                        if inputs.nth(idx).is_visible():
                                            any_visible_inputs = True
                                            break
                                except Exception:
                                    continue
                                if any_visible_inputs:
                                    break
                            
                            # Disappeared form inputs only count as success if NO spam or errors detected
                            if not any_visible_inputs and not has_validation_errors and not has_spam_banner:
                                submitted = True
                                add_log("8_SUBMISSION", "Formulaire disparu (champs invisibles). Soumission probablement réussie.", "SUCCESS")
                        except Exception:
                            pass
                        
                        if not submitted:
                            add_log("8_SUBMISSION", "La page du formulaire est toujours active ou contient des erreurs. Soumission incomplète.", "WARNING")

                # Screenshot 3: Final result (taken after verification wait to see confirmation or errors)
                img3_rel = f"/static/{rel_dir}/step3_result.png"
                img3_abs = os.path.join(abs_dir, "step3_result.png")
                take_resilient_screenshot(page, img3_abs, img3_rel, "step3_result")

                browser.close()

                if submitted:
                    add_log("8_SUBMISSION", "Candidature soumise avec succès !", "SUCCESS")
                    return {
                        "success": True,
                        "status": "SENT",
                        "error_message": None,
                        "cover_letter": cover_letter,
                        "execution_logs": logs,
                        "screenshots": screenshots
                    }
                else:
                    add_log("8_SUBMISSION", "La soumission automatique n'a pas pu être finalisée. Soumission manuelle requise pour les champs restants.", "WARNING")
                    return {
                        "success": True,
                        "status": "MANUAL_REQUIRED",
                        "error_message": error_msg,
                        "cover_letter": cover_letter,
                        "execution_logs": logs,
                        "screenshots": screenshots
                    }

        except Exception as e:
            logger.error(f"Playwright execution failed: {e}", exc_info=True)
            add_log("ERROR", f"Erreur fatale lors de l'exécution de l'agent : {str(e)}", "ERROR")
            return {
                "success": False,
                "status": "FAILED",
                "error_message": str(e),
                "cover_letter": cover_letter,
                "execution_logs": logs,
                "screenshots": screenshots
            }
