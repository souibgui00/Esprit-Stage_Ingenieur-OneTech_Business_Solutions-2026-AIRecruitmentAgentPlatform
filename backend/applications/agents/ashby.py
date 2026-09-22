import time
import os
from typing import List, Any, Dict, Optional
from applications.agents.base import BasePlatformAgent


class AshbyAgent(BasePlatformAgent):
    """
    Agent specialized in Ashby HQ job boards (careers.ashbyhq.com or similar self-hosted).
    Ashby uses a tabbed layout: 'Job Description' | 'Apply' tabs.
    After clicking Apply, a form is revealed — either inline (Gem widget) or in an iframe.
    Uses AI (Groq LLM) to intelligently fill custom fields.
    """

    def detect(self, page, url: str) -> bool:
        # Detect Ashby by URL, tab structure, global objects, or iframes
        url_lower = url.lower()
        if "ashbyhq.com" in url_lower or "ashby" in url_lower:
            return True
        try:
            # Check for Ashby global object or ashby specific classes
            is_ashby = page.evaluate("() => typeof window.Ashby !== 'undefined' || document.querySelector('.ashby-job-board') !== null")
            if is_ashby:
                return True
                
            # Check for tabs
            tab = page.query_selector("button:has-text('Apply'), a:has-text('Apply')")
            desc_tab = page.query_selector("button:has-text('Job Description'), a:has-text('Job Description')")
            if tab and desc_tab:
                return True
                
            # Check for ashby iframe
            for frame in page.frames:
                if "ashbyhq.com" in (frame.url or "").lower():
                    return True
        except Exception:
            pass
        return False

    def _get_form_context(self, page, add_log):
        """
        After Apply tab is clicked, find the best context for form filling.
        Checks for iframe (ashby/gem), then falls back to main page.
        """
        all_frames = page.frames
        add_log("FILL_ASHBY", f"{len(all_frames)} frame(s) détectée(s) sur la page.", "INFO")

        for frame in all_frames:
            frame_url = frame.url or ""
            if frame_url and frame_url != "about:blank" and frame_url != page.url:
                add_log("FILL_ASHBY", f"Frame externe : {frame_url}", "INFO")
                try:
                    test_el = frame.query_selector("input, textarea")
                    if test_el:
                        add_log("FILL_ASHBY", f"Formulaire trouvé dans la frame : {frame_url}", "SUCCESS")
                        return frame, ("gem" in frame_url.lower())
                except Exception:
                    continue

        # No external frame found — form is inline in the main page
        add_log("FILL_ASHBY", "Formulaire inline détecté dans la page principale.", "INFO")
        return page, False

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
        add_log("FILL_ASHBY", "Interface Ashby détectée. Clic sur l'onglet 'Apply'...")
        fields_filled = 0
        pending_questions = []

        # Step 1: Click the Apply tab
        try:
            apply_tab = page.query_selector("button:has-text('Apply'), a:has-text('Apply')")
            if apply_tab and apply_tab.is_visible():
                apply_tab.click()
                add_log("FILL_ASHBY", "Onglet 'Apply' cliqué. Attente du chargement du formulaire (6s)...", "SUCCESS")
                time.sleep(6)
                
                # Screenshot: After clicking Apply tab
                try:
                    if hasattr(page, '_screenshots') and hasattr(page, '_screenshot_dir'):
                        screenshot_dir = page._screenshot_dir
                        screenshot_dict = page._screenshots
                        
                        after_apply_screenshot = f"/static/{screenshot_dir}/ashby_after_apply.png"
                        after_apply_abs = os.path.join("/app/static", screenshot_dir, "ashby_after_apply.png")
                        try:
                            page.screenshot(path=after_apply_abs, full_page=True, timeout=60000)
                        except Exception:
                            # Fallback to non-full-page screenshot
                            page.screenshot(path=after_apply_abs, timeout=60000)
                        screenshot_dict["ashby_after_apply"] = after_apply_screenshot
                        add_log("FILL_ASHBY", "Capture d'écran : formulaire après clic Apply", "INFO")
                except Exception as e:
                    add_log("FILL_ASHBY", f"Impossible de capturer après clic Apply : {str(e)}", "WARNING")
                    
            else:
                add_log("FILL_ASHBY", "Onglet 'Apply' non trouvé. Recherche directe des champs...", "WARNING")
                time.sleep(2)
        except Exception as e:
            add_log("FILL_ASHBY", f"Erreur clic onglet Apply : {str(e)}", "WARNING")

        # Step 2: Resolve form context (iframe or main page)
        form_ctx, is_gem = self._get_form_context(page, add_log)

        # Step 3: If Gem detected in frame URL, delegate to GemAgent
        if is_gem:
            add_log("FILL_ASHBY", "Widget Gem.com détecté. Délégation au GemAgent...", "SUCCESS")
            from applications.agents.gem import GemAgent
            return GemAgent().fill_form(page, cv, personal_info, cover_letter, skills, experiences, add_log, user_responses)

        # Step 4: Check if inline form looks like Gem (by page content)
        try:
            page_content = page.content().lower()
            if "gem.com" in page_content or "powered by gem" in page_content:
                add_log("FILL_ASHBY", "Widget Gem inline détecté dans le DOM. Délégation au GemAgent...", "SUCCESS")
                from applications.agents.gem import GemAgent
                return GemAgent().fill_form(page, cv, personal_info, cover_letter, skills, experiences, add_log, user_responses)
        except Exception:
            pass

        # Step 5: Fill standard Ashby fields in the resolved context
        candidate_name = personal_info.full_name if personal_info and personal_info.full_name else ""
        email_to_use = personal_info.email if personal_info and personal_info.email else ""
        phone_to_use = personal_info.phone if personal_info and personal_info.phone else ""

        # Extract CV text and LinkedIn for AI-powered filling
        cv_text = self.get_cv_text(cv)
        linkedin_url = getattr(personal_info, "linkedin_url", "") or ""
        if not linkedin_url and cv_text:
            linkedin_url = self.extract_linkedin(cv_text)

        first_name, last_name = "", ""
        if candidate_name and " " in candidate_name:
            first_name, last_name = candidate_name.split(" ", 1)
        else:
            first_name = candidate_name

        field_mappings = [
            (["input[name='name']", "input[placeholder*='name' i]", "input[id*='name' i]"], candidate_name, "Nom complet"),
            (["input[name='firstName']", "input[placeholder*='first' i]", "input[id*='first' i]"], first_name, "Prénom"),
            (["input[name='lastName']", "input[placeholder*='last' i]", "input[id*='last' i]"], last_name, "Nom"),
            (["input[type='email']", "input[name='email']", "input[placeholder*='email' i]"], email_to_use, "Email"),
            (["input[placeholder*='linkedin' i]", "input[name*='linkedin' i]", "input[type='url']"], linkedin_url, "LinkedIn"),
            (["input[type='tel']", "input[name='phone']", "input[placeholder*='phone' i]"], phone_to_use, "Téléphone"),
            (["textarea[name='coverLetter']", "textarea[placeholder*='cover' i]", "textarea[placeholder*='letter' i]", "textarea"], cover_letter, "Lettre de motivation"),
        ]

        for selectors, value, label in field_mappings:
            if not value:
                continue
            for sel in selectors:
                try:
                    el = form_ctx.query_selector(sel)
                    if el and el.is_visible():
                        el.click()
                        time.sleep(0.2)
                        el.fill(value)
                        fields_filled += 1
                        add_log("FILL_ASHBY", f"✅ Champ '{label}' rempli.", "SUCCESS")
                        break
                except Exception:
                    continue

        # Step 6: CV upload
        try:
            for sel in ["input[type='file'][name*='resume' i]", "input[type='file'][name*='cv' i]", "input[type='file']"]:
                el = form_ctx.query_selector(sel)
                if el and cv and cv.raw_file_url and not cv.raw_file_url.startswith("http"):
                    abs_cv_path = f"/app/{cv.raw_file_url}"
                    if os.path.exists(abs_cv_path):
                        el.set_input_files(abs_cv_path)
                        fields_filled += 1
                        add_log("FILL_ASHBY", f"✅ CV uploadé : {cv.filename}", "SUCCESS")
                        break
        except Exception as e:
            add_log("FILL_ASHBY", f"⚠️ Échec upload CV : {str(e)}", "WARNING")

        # Step 7: AI-powered custom field filling (textareas, radios, remaining inputs)
        if cv_text:
            add_log("FILL_ASHBY", "🤖 Phase IA : Analyse des questions personnalisées...", "INFO")

            # Fill empty textareas
            try:
                textareas = form_ctx.query_selector_all("textarea")
                for ta in textareas:
                    if not ta.is_visible():
                        continue
                    current_val = ta.input_value()
                    if current_val and len(current_val.strip()) > 5:
                        continue
                    placeholder = ta.get_attribute("placeholder") or ""
                    
                    # Look up label from DOM context if placeholder is missing
                    ta_label = ""
                    try:
                        ta_label = ta.evaluate(r"""el => {
                            if (el.id) {
                                const l = document.querySelector('label[for="' + el.id + '"]');
                                if (l) return l.textContent.trim();
                            }
                            const p = el.closest('label');
                            if (p) return p.textContent.trim();
                            const c = el.closest('.field') || el.closest('[class*="field"]') || el.closest('[class*="question"]') || el.parentElement;
                            if (c) {
                                const l = c.querySelector('label, [class*="label"], span, p, h3, h4');
                                if (l && l !== el) return l.textContent.trim();
                            }
                            return '';
                        }""") or ""
                    except Exception:
                        pass
                    
                    question = ta_label or placeholder or "Why are you a strong fit for this role?"
                    label = ta_label or placeholder or "Additional Information"
                    
                    # Check if user has provided an answer
                    field_id = self._get_field_id(ta)
                    if user_responses and field_id in user_responses:
                        answer = user_responses[field_id]
                        add_log("FILL_ASHBY", f"✅ Utilisation de la réponse utilisateur pour : {field_id}", "SUCCESS")
                    else:
                        answer = self.ask_llm(question, cv_text, cover_letter)
                    
                    if answer and answer.lower() not in ("none", "n/a", ""):
                        ta.fill(answer, timeout=3000)
                        fields_filled += 1
                        add_log("FILL_ASHBY", f"✅ 🤖 Textarea '{label[:30]}' rempli par IA.", "SUCCESS")
                    else:
                        # Add to pending questions if it looks important
                        is_required = self._is_field_required(ta)
                        if is_required or any(keyword in label.lower() for keyword in ["salary", "cover", "motivation", "why"]):
                            pending_questions.append(self._build_pending_question(field_id, label, "textarea", is_required))
                            add_log("FILL_ASHBY", f"⚠️ Question en attente : {label}", "WARNING")
            except Exception as e:
                add_log("FILL_ASHBY", f"⚠️ Erreur IA textareas : {str(e)[:80]}", "WARNING")

            # Handle radio buttons
            try:
                radio_elements = form_ctx.query_selector_all("input[type='radio']")
                if radio_elements:
                    radio_groups = {}
                    for radio in radio_elements:
                        try:
                            info = radio.evaluate(r'''r => {
                                let optLabel = '';
                                if (r.id) {
                                    const lbl = document.querySelector('label[for="' + r.id + '"]');
                                    if (lbl) optLabel = lbl.innerText.trim();
                                }
                                if (!optLabel) {
                                    const p = r.closest('label');
                                    if (p) optLabel = p.innerText.trim();
                                }
                                let question = '';
                                const container = r.closest('fieldset') || r.closest('[class*="question"]') || r.closest('[class*="field"]') || r.closest('[class*="group"]');
                                if (container) {
                                    const legend = container.querySelector('legend, label:not([for]), p, span, h3, h4');
                                    if (legend) question = legend.innerText.trim();
                                }
                                if (!question) {
                                    let el = r.closest('div');
                                    while (el) {
                                        const prev = el.previousElementSibling;
                                        if (prev && prev.innerText && prev.innerText.trim().length > 3) {
                                            question = prev.innerText.trim();
                                            break;
                                        }
                                        el = el.parentElement;
                                    }
                                }
                                return { name: r.name, optLabel, question };
                            }''')
                            name = info.get('name')
                            if not name:
                                continue
                            if name not in radio_groups:
                                radio_groups[name] = {'question': info.get('question') or name, 'options': []}
                            radio_groups[name]['options'].append({'label': info.get('optLabel') or '', 'element': radio})
                            if info.get('question') and not radio_groups[name]['question']:
                                radio_groups[name]['question'] = info['question']
                        except Exception:
                            continue

                    for name, group_data in radio_groups.items():
                        question = group_data['question']
                        options = [opt for opt in group_data['options'] if opt['label']]
                        opt_labels = [opt['label'] for opt in options]
                        if not question or not opt_labels:
                            continue
                        field_id = question.lower().replace(" ", "_").replace("?", "")[:40]
                        if user_responses and field_id in user_responses:
                            chosen = user_responses[field_id]
                            add_log("FILL_ASHBY", f"✅ Utilisation de la réponse utilisateur pour : {field_id}", "SUCCESS")
                        else:
                            chosen = self.ask_llm_choose_option(question, opt_labels, cv_text)

                        clicked = False
                        if chosen:
                            for opt in options:
                                if chosen.lower() in opt['label'].lower() or opt['label'].lower() in chosen.lower():
                                    try:
                                        opt['element'].click(force=True, timeout=3000)
                                        fields_filled += 1
                                        clicked = True
                                        add_log("FILL_ASHBY", f"✅ Radio cliqué : '{opt['label']}'", "SUCCESS")
                                        break
                                    except Exception:
                                        pass
                        if not clicked:
                            is_required = self._is_radio_group_required(form_ctx, question)
                            if is_required or any(keyword in question.lower() for keyword in ["sponsorship", "visa", "work authorization", "contract"]):
                                pending_questions.append(self._build_pending_question(field_id, question, "radio", is_required, opt_labels))
                                add_log("FILL_ASHBY", f"⚠️ Question en attente : {question}", "WARNING")
            except Exception as e:
                add_log("FILL_ASHBY", f"⚠️ Erreur IA radios : {str(e)[:80]}", "WARNING")

            # Handle select dropdowns
            try:
                selects = form_ctx.query_selector_all("select")
                for sel in selects:
                    if not sel.is_visible():
                        continue
                    current_val = sel.input_value()
                    if current_val:
                        continue
                    
                    field_id = self._get_field_id(sel)
                    label = sel.get_attribute("name") or sel.get_attribute("id") or "Dropdown"
                    
                    # Get options
                    options = []
                    for opt in sel.query_selector_all("option"):
                        opt_text = opt.inner_text().strip()
                        if opt_text and opt_text not in ["", "Select...", "Choose..."]:
                            options.append(opt_text)
                    
                    # Check if user has provided an answer
                    if user_responses and field_id in user_responses:
                        chosen = user_responses[field_id]
                        add_log("FILL_ASHBY", f"✅ Utilisation de la réponse utilisateur pour : {field_id}", "SUCCESS")
                    else:
                        # Try to choose via LLM
                        if options:
                            chosen = self.ask_llm_choose_option(label, options, cv_text)
                        else:
                            chosen = None
                    
                    if chosen and chosen in options:
                        sel.select_option(chosen)
                        fields_filled += 1
                        add_log("FILL_ASHBY", f"✅ Dropdown rempli : {label}", "SUCCESS")
                    else:
                        # Add to pending questions if required
                        is_required = self._is_field_required(sel)
                        if is_required:
                            pending_questions.append(self._build_pending_question(field_id, label, "select", is_required, options))
                            add_log("FILL_ASHBY", f"⚠️ Question en attente : {label}", "WARNING")
            except Exception as e:
                add_log("FILL_ASHBY", f"⚠️ Erreur IA selects : {str(e)[:80]}", "WARNING")

        # Screenshot: After form filling
        try:
            if hasattr(page, '_screenshots') and hasattr(page, '_screenshot_dir'):
                screenshot_dir = page._screenshot_dir
                screenshot_dict = page._screenshots
                
                after_fill_screenshot = f"/static/{screenshot_dir}/ashby_after_fill.png"
                after_fill_abs = os.path.join("/app/static", screenshot_dir, "ashby_after_fill.png")
                try:
                    page.screenshot(path=after_fill_abs, full_page=True, timeout=60000)
                except Exception:
                    # Fallback to non-full-page screenshot
                    page.screenshot(path=after_fill_abs, timeout=60000)
                screenshot_dict["ashby_after_fill"] = after_fill_screenshot
                add_log("FILL_ASHBY", "Capture d'écran : formulaire après remplissage", "INFO")
        except Exception as e:
            add_log("FILL_ASHBY", f"Impossible de capturer après remplissage : {str(e)}", "WARNING")

        return {
            "success": fields_filled > 0,
            "pending_questions": pending_questions
        }

    def _is_field_required(self, element) -> bool:
        """Check if a form field is marked as required."""
        try:
            # Check required attribute
            if element.get_attribute("required"):
                return True
            # Check for required class
            class_attr = element.get_attribute("class") or ""
            if "required" in class_attr.lower():
                return True
            # Check for aria-required
            if element.get_attribute("aria-required") == "true":
                return True
            # Check label for asterisk
            try:
                label = element.evaluate("el => { const labels = el.labels; return labels && labels.length > 0 ? labels[0].textContent : ''; }")
                if label and "*" in label:
                    return True
            except Exception:
                pass
            return False
        except Exception:
            return False

    def _is_radio_group_required(self, form_ctx, question_text: str) -> bool:
        """Check if a radio button group is required."""
        try:
            # Find the radio inputs for this question
            # This is a heuristic - in practice, you'd need to match the question to its container
            radios = form_ctx.query_selector_all("input[type='radio']")
            for radio in radios:
                # Check if any radio in the group is marked required
                if self._is_field_required(radio):
                    return True
            return False
        except Exception:
            return False

    def submit_form(self, page, add_log) -> bool:
        # If Gem widget is present, delegate submission to GemAgent
        try:
            has_gem = False
            for frame in page.frames:
                if frame.url and "gem.com" in frame.url:
                    has_gem = True
                    break
            if not has_gem:
                page_content = page.content().lower()
                if "gem.com" in page_content or "powered by gem" in page_content:
                    has_gem = True

            if has_gem:
                add_log("SUBMIT_ASHBY", "Formulaire Gem détecté lors de la soumission. Délégation au GemAgent...", "INFO")
                from applications.agents.gem import GemAgent
                return GemAgent().submit_form(page, add_log)
        except Exception as e:
            add_log("SUBMIT_ASHBY", f"Erreur lors de la vérification de délégation : {str(e)}", "WARNING")

        contexts = [page] + list(page.frames)
        for ctx in contexts:
            for sel in ["button[type='submit']", "button:has-text('Submit')", "button:has-text('Apply')", "input[type='submit']"]:
                try:
                    btn = ctx.query_selector(sel)
                    if btn:
                        try:
                            btn.scroll_into_view_if_needed()
                        except Exception:
                            pass

                        add_log("SUBMIT_ASHBY", f"Bouton soumission trouvé ({sel}). Clic...", "INFO")
                        btn.click(force=True, timeout=5000)
                        time.sleep(4)
                        
                        # Screenshot: After submission
                        try:
                            if hasattr(page, '_screenshots') and hasattr(page, '_screenshot_dir'):
                                screenshot_dir = page._screenshot_dir
                                screenshot_dict = page._screenshots
                                
                                after_submit_screenshot = f"/static/{screenshot_dir}/ashby_after_submit.png"
                                after_submit_abs = os.path.join("/app/static", screenshot_dir, "ashby_after_submit.png")
                                try:
                                    page.screenshot(path=after_submit_abs, full_page=True, timeout=60000)
                                except Exception:
                                    # Fallback to non-full-page screenshot
                                    page.screenshot(path=after_submit_abs, timeout=60000)
                                screenshot_dict["ashby_after_submit"] = after_submit_screenshot
                                add_log("SUBMIT_ASHBY", "Capture d'écran : page après soumission", "INFO")
                        except Exception as e:
                            add_log("SUBMIT_ASHBY", f"Impossible de capturer après soumission : {str(e)}", "WARNING")
                        
                        return True
                except Exception:
                    pass
        return False
