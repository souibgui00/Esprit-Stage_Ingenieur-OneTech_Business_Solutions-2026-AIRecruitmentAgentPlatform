import time
from typing import List, Any, Dict, Optional
from applications.agents.base import BasePlatformAgent

class GenericAgent(BasePlatformAgent):
    """
    Fallback agent that uses heuristics to identify and fill fields on any web page.
    """

    def detect(self, page, url: str) -> bool:
        # Fallback agent, always returns True if no other agent is selected
        return True

    def fill_form(
        self,
        page,
        cv,
        personal_info,
        cover_letter: str,
        skills: List[str],
        experiences: List[Any],
        add_log,
        user_responses: Optional[Dict[str, str]] = None
    ) -> dict:
        add_log("FILL_GENERIC", "Détection heuristique des champs sur la page...")
        fields_filled = 0
        email_filled = False
        pending_questions = []

        candidate_name = personal_info.full_name if personal_info and personal_info.full_name else "Candidat"
        email_to_use = personal_info.email if personal_info and personal_info.email else ""
        phone_to_use = personal_info.phone if personal_info and personal_info.phone else ""

        # Name field
        name_selectors = [
            "input[name*='name']", "input[placeholder*='name']", "input[placeholder*='nom']",
            "input[id*='name']", "input[type='text'][autocomplete*='name']"
        ]
        for sel in name_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.fill(candidate_name)
                    fields_filled += 1
                    add_log("FILL_GENERIC", f"Champ Nom rempli avec : '{candidate_name}'")
                    break
            except Exception:
                pass

        # Email field
        email_selectors = [
            "input[type='email']", "input[name*='email']", "input[placeholder*='email']",
            "input[id*='email']"
        ]
        for sel in email_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.fill(email_to_use)
                    fields_filled += 1
                    email_filled = True
                    add_log("FILL_GENERIC", f"Champ Email rempli avec : '{email_to_use}'")
                    break
            except Exception:
                pass

        # Phone field
        phone_selectors = [
            "input[type='tel']", "input[name*='phone']", "input[placeholder*='phone']",
            "input[placeholder*='téléphone']", "input[id*='phone']"
        ]
        for sel in phone_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.fill(phone_to_use)
                    fields_filled += 1
                    add_log("FILL_GENERIC", f"Champ Téléphone rempli avec : '{phone_to_use}'")
                    break
            except Exception:
                pass

        # LinkedIn and GitHub/Portfolio URLs
        cv_text = self.get_cv_text(cv) if cv else ""
        linkedin_url = getattr(personal_info, "linkedin_url", "") or ""
        github_url = getattr(personal_info, "github_url", "") or ""
        if not linkedin_url and cv_text:
            linkedin_url = self.extract_linkedin(cv_text)
        if not github_url and cv_text:
            github_url = self.extract_github(cv_text)

        if linkedin_url:
            linkedin_selectors = [
                "input[name*='linkedin' i]", "input[placeholder*='linkedin' i]",
                "input[id*='linkedin' i]", "input[aria-label*='linkedin' i]"
            ]
            for sel in linkedin_selectors:
                try:
                    el = page.query_selector(sel)
                    if el and el.is_visible():
                        el.fill(linkedin_url)
                        fields_filled += 1
                        add_log("FILL_GENERIC", f"Champ LinkedIn rempli avec : '{linkedin_url}'")
                        break
                except Exception:
                    pass

        if github_url:
            github_selectors = [
                "input[name*='github' i]", "input[placeholder*='github' i]",
                "input[id*='github' i]", "input[placeholder*='portfolio' i]",
                "input[name*='portfolio' i]", "input[placeholder*='website' i]",
                "input[name*='website' i]"
            ]
            for sel in github_selectors:
                try:
                    el = page.query_selector(sel)
                    if el and el.is_visible():
                        el.fill(github_url)
                        fields_filled += 1
                        add_log("FILL_GENERIC", f"Champ GitHub/Portfolio rempli avec : '{github_url}'")
                        break
                except Exception:
                    pass

        # Cover letter field
        cover_selectors = [
            "textarea", "textarea[name*='cover']", "textarea[name*='letter']",
            "textarea[name*='message']", "textarea[placeholder*='Cover']", "textarea[placeholder*='motivation']"
        ]
        for sel in cover_selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.fill(cover_letter)
                    fields_filled += 1
                    add_log("FILL_GENERIC", "Lettre de motivation injectée dans le champ texte.")
                    break
            except Exception:
                pass

        # CV File upload field
        try:
            file_selectors = [
                "input[type='file'][name*='resume']", "input[type='file'][name*='cv']",
                "input[type='file'][id*='resume']", "input[type='file'][id*='cv']",
                "input[type='file']"
            ]
            for sel in file_selectors:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    cv_path = cv.raw_file_url
                    if cv_path and not cv_path.startswith("http") and "/" in cv_path:
                        abs_cv_path = f"/app/{cv_path}"
                        import os
                        if os.path.exists(abs_cv_path):
                            el.set_input_files(abs_cv_path)
                            fields_filled += 1
                            add_log("FILL_GENERIC", f"CV téléchargé via sélecteur ({sel}) : {cv.filename}", "SUCCESS")
                            break
        except Exception as e:
            add_log("FILL_GENERIC", f"Échec de l'upload du CV : {str(e)}", "WARNING")

        # Defensive check: If only email was filled, this might be a newsletter/listing page
        if fields_filled == 1 and email_filled:
            add_log("FILL_GENERIC", "ATTENTION: Seul le champ email a été rempli. Ceci peut être un formulaire d'inscription/newsletter et non un formulaire de candidature.", "WARNING")
            
            # Check if page still looks like a job listing
            page_content = page.content().lower()
            job_listing_indicators = ["job", "position", "role", "company", "salary", "location", "apply", "application"]
            listing_score = sum(1 for indicator in job_listing_indicators if indicator in page_content)
            
            # Specific check for "Apply on company site" buttons - indicates we're still on a listing page
            external_apply_indicators = [
                "apply on company site",
                "apply on company website", 
                "apply externally",
                "apply on company"
            ]
            has_external_apply = any(indicator in page_content for indicator in external_apply_indicators)
            
            if listing_score >= 3 or has_external_apply:  # If page has job listing indicators OR external apply button
                reason = "listing page" if listing_score >= 3 else "external apply button present"
                add_log("FILL_GENERIC", f"La page ressemble encore à une offre d'emploi/listing ({reason}). Rejet du remplissage du seul champ email.", "WARNING")
                return {"success": False, "pending_questions": []}

        # Detect and collect pending important questions
        try:
            # Look for required text inputs that weren't filled
            all_inputs = page.query_selector_all("input[type='text'], input[type='number'], input:not([type])")
            for inp in all_inputs:
                if not inp.is_visible():
                    continue
                current_val = inp.input_value()
                if current_val and len(current_val.strip()) > 0:
                    continue
                
                # Check if it's an important/required field
                is_required = self._is_field_required(inp)
                placeholder = inp.get_attribute("placeholder") or ""
                name = inp.get_attribute("name") or ""
                id_attr = inp.get_attribute("id") or ""
                
                # Identify important fields
                important_keywords = ["salary", "cover", "motivation", "why", "experience", "sponsorship", "visa", "contract"]
                label = placeholder or name or id_attr or "Additional Information"
                
                if is_required or any(keyword in label.lower() for keyword in important_keywords):
                    field_id = self._get_field_id(inp)
                    # Check if user provided an answer
                    if user_responses and field_id in user_responses:
                        inp.fill(user_responses[field_id])
                        fields_filled += 1
                        add_log("FILL_GENERIC", f"✅ Utilisation de la réponse utilisateur pour : {field_id}", "SUCCESS")
                    else:
                        pending_questions.append(self._build_pending_question(field_id, label, "text", is_required))
                        add_log("FILL_GENERIC", f"⚠️ Question en attente : {label}", "WARNING")
            
            # Look for required textareas that weren't filled
            all_textareas = page.query_selector_all("textarea")
            for ta in all_textareas:
                if not ta.is_visible():
                    continue
                current_val = ta.input_value()
                if current_val and len(current_val.strip()) > 5:
                    continue
                
                is_required = self._is_field_required(ta)
                placeholder = ta.get_attribute("placeholder") or ""
                label = placeholder or "Additional Information"
                
                if is_required or any(keyword in label.lower() for keyword in ["salary", "cover", "motivation", "why"]):
                    field_id = self._get_field_id(ta)
                    if user_responses and field_id in user_responses:
                        ta.fill(user_responses[field_id])
                        fields_filled += 1
                        add_log("FILL_GENERIC", f"✅ Utilisation de la réponse utilisateur pour : {field_id}", "SUCCESS")
                    else:
                        pending_questions.append(self._build_pending_question(field_id, label, "textarea", is_required))
                        add_log("FILL_GENERIC", f"⚠️ Question en attente : {label}", "WARNING")
            
            # Look for required selects that weren't filled
            all_selects = page.query_selector_all("select")
            for sel in all_selects:
                if not sel.is_visible():
                    continue
                current_val = sel.input_value()
                if current_val:
                    continue
                
                is_required = self._is_field_required(sel)
                name = sel.get_attribute("name") or ""
                label = name or "Dropdown"
                
                if is_required:
                    field_id = self._get_field_id(sel)
                    # Get options
                    options = []
                    for opt in sel.query_selector_all("option"):
                        opt_text = opt.inner_text().strip()
                        if opt_text and opt_text not in ["", "Select...", "Choose..."]:
                            options.append(opt_text)
                    
                    if user_responses and field_id in user_responses:
                        chosen = user_responses[field_id]
                        if chosen in options:
                            sel.select_option(chosen)
                            fields_filled += 1
                            add_log("FILL_GENERIC", f"✅ Utilisation de la réponse utilisateur pour : {field_id}", "SUCCESS")
                    else:
                        pending_questions.append(self._build_pending_question(field_id, label, "select", is_required, options))
                        add_log("FILL_GENERIC", f"⚠️ Question en attente : {label}", "WARNING")
        except Exception as e:
            add_log("FILL_GENERIC", f"⚠️ Erreur lors de la détection des questions en attente : {str(e)[:80]}", "WARNING")

        return {
            "success": fields_filled > 0,
            "pending_questions": pending_questions
        }

    def _is_field_required(self, element) -> bool:
        """Check if a form field is marked as required."""
        try:
            if element.get_attribute("required"):
                return True
            class_attr = element.get_attribute("class") or ""
            if "required" in class_attr.lower():
                return True
            if element.get_attribute("aria-required") == "true":
                return True
            try:
                label = element.evaluate("el => { const labels = el.labels; return labels && labels.length > 0 ? labels[0].textContent : ''; }")
                if label and "*" in label:
                    return True
            except Exception:
                pass
            return False
        except Exception:
            return False

    def submit_form(self, page, add_log) -> bool:
        submit_selectors = [
            "button[type='submit']", "input[type='submit']", "button:has-text('Submit')",
            "button:has-text('Postuler')", "button:has-text('Send')", "input:has-text('Submit')"
        ]
        for sel in submit_selectors:
            try:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    add_log("SUBMIT_GENERIC", f"Bouton de soumission détecté ({sel}). Clic en cours...")
                    btn.click()
                    time.sleep(3)
                    return True
            except Exception:
                pass
        return False
