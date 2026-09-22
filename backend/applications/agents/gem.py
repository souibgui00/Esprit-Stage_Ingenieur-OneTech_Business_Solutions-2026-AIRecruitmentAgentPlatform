import time
import os
import json
from typing import List, Any, Dict, Optional
from applications.agents.base import BasePlatformAgent


class GemAgent(BasePlatformAgent):
    """
    Agent specialized in Gem-powered job application forms (widget.gem.com / jobs.gem.com).
    Uses AI (Groq LLM) to intelligently fill ALL form fields including:
    - Standard fields (name, email, phone, LinkedIn)
    - Custom text questions (e.g. "Why are you a strong fit?")
    - Radio buttons / checkboxes (e.g. "B2B contract?", "sponsorship?")
    - Salary expectations
    """

    def detect(self, page, url: str) -> bool:
        if "gem.com" in url.lower():
            return True
        try:
            for frame in page.frames:
                if "gem.com" in (frame.url or "").lower():
                    return True
            page_content = page.content().lower()
            if "powered by gem" in page_content or "widget.gem.com" in page_content:
                return True
        except Exception:
            pass
        return False

    def _get_form_context(self, page, add_log):
        """Returns the frame or page context containing the Gem form.
        Gem can render inline (main page) or inside an iframe."""

        # First: check if the main page itself has the form inputs (inline widget)
        try:
            test_el = page.query_selector("input[placeholder*='first' i], input[placeholder*='email' i]")
            if test_el and test_el.is_visible():
                add_log("FILL_GEM", "Formulaire Gem inline trouvé dans la page principale.", "SUCCESS")
                return page
        except Exception:
            pass

        # Second: look in external frames for gem.com
        try:
            for frame in page.frames:
                if frame.url and "gem.com" in frame.url and "blank" not in frame.url:
                    add_log("FILL_GEM", f"Contexte Gem trouvé dans iframe : {frame.url}", "SUCCESS")
                    return frame
            # Third: find any frame with input fields
            for frame in page.frames:
                try:
                    if frame.query_selector("input"):
                        add_log("FILL_GEM", f"Formulaire trouvé dans frame : {frame.url}", "INFO")
                        return frame
                except Exception:
                    continue
        except Exception as e:
            add_log("FILL_GEM", f"Erreur recherche contexte : {str(e)}", "WARNING")

        # Fallback: main page
        add_log("FILL_GEM", "Fallback sur la page principale.", "INFO")
        return page

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
        add_log("FILL_GEM", "Formulaire Gem détecté. Localisation du contexte...")
        fields_filled = 0

        time.sleep(3)
        form_ctx = self._get_form_context(page, add_log)

        # ── Wait for the iframe/form to actually render its inputs AND labels ──
        add_log("FILL_GEM", "Attente du chargement complet du formulaire Gem...", "INFO")
        # Step 1: Wait for at least one input to appear
        for attempt in range(10):
            try:
                test = form_ctx.query_selector("input:not([type='hidden']):not([type='file'])")
                if test:
                    break
            except Exception:
                pass
            time.sleep(1)
        else:
            add_log("FILL_GEM", "Le formulaire n'a pas chargé ses champs après 10s.", "WARNING")

        # Step 2: Wait for labels to render (Gem React renders labels AFTER inputs)
        for attempt in range(8):
            try:
                has_label = form_ctx.evaluate(r'''
                    (() => {
                        const labels = document.querySelectorAll('label');
                        return labels.length > 0 && labels[0].textContent.trim().length > 0;
                    })()
                ''')
                if has_label:
                    add_log("FILL_GEM", "Labels du formulaire détectés.", "SUCCESS")
                    break
            except Exception:
                pass
            time.sleep(1)
        else:
            add_log("FILL_GEM", "Labels non détectés après 8s, tentative de remplissage quand même.", "WARNING")

        # Final stabilization pause
        time.sleep(2)

        # ── Extract candidate data ──
        candidate_name = personal_info.full_name if personal_info and personal_info.full_name else ""
        email_to_use = personal_info.email if personal_info and personal_info.email else ""
        phone_to_use = personal_info.phone if personal_info and personal_info.phone else ""

        first_name, last_name = "", ""
        if candidate_name and " " in candidate_name:
            first_name, last_name = candidate_name.split(" ", 1)
        else:
            first_name = candidate_name

        salary_expectation = getattr(personal_info, 'salary_expectation', '') or ''

        # ── Extract CV text for AI-powered filling ──
        cv_text = self.get_cv_text(cv)
        if cv_text:
            add_log("FILL_GEM", f"Texte du CV extrait ({len(cv_text)} caractères).", "SUCCESS")
        else:
            add_log("FILL_GEM", "Impossible d'extraire le texte du CV.", "WARNING")

        # ── Extract real LinkedIn URL from CV or profile ──
        linkedin_url = getattr(personal_info, "linkedin_url", "") or ""
        if not linkedin_url and cv_text:
            linkedin_url = self.extract_linkedin(cv_text)
            if linkedin_url:
                add_log("FILL_GEM", f"LinkedIn extrait du CV : {linkedin_url}", "SUCCESS")

        # ── Extract GitHub/Portfolio from CV or profile ──
        github_url = getattr(personal_info, "github_url", "") or ""
        if not github_url and cv_text:
            github_url = self.extract_github(cv_text)
            if github_url:
                add_log("FILL_GEM", f"Portfolio/GitHub extrait du CV : {github_url}", "SUCCESS")

        # ══════════════════════════════════════════════════════════
        # PHASE 1: Scan form fields (with retry for label rendering)
        # ══════════════════════════════════════════════════════════
        add_log("FILL_GEM", "Phase 1: Scanning form fields...", "INFO")

        scan_result = []
        labels_found = False

        # Retry scan up to 3 times — Gem's React renders labels AFTER inputs
        for scan_attempt in range(3):
            try:
                scan_result = form_ctx.evaluate(r'''
                (() => {
                    const results = [];
                    const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="file"]):not([type="radio"]):not([type="checkbox"]), textarea');
                    inputs.forEach((el, idx) => {
                        let label = '';
                        // Strategy 1: label[for=id]
                        if (el.id) {
                            const lbl = document.querySelector('label[for="' + el.id + '"]');
                            if (lbl) label = lbl.textContent.trim();
                        }
                        // Strategy 2: closest label parent
                        if (!label) {
                            const p = el.closest('label');
                            if (p) label = p.textContent.trim();
                        }
                        // Strategy 3: previous sibling text
                        if (!label) {
                            let prev = el.previousElementSibling;
                            if (prev) label = prev.textContent.trim();
                        }
                        // Strategy 4: parent container
                        if (!label) {
                            const c = el.parentElement;
                            if (c) {
                                const l = c.querySelector('label, span, p');
                                if (l && l !== el) label = l.textContent.trim();
                            }
                        }
                        // Strategy 5: grandparent
                        if (!label) {
                            const gp = el.parentElement?.parentElement;
                            if (gp) {
                                const l = gp.querySelector('label, span, p');
                                if (l) label = l.textContent.trim();
                            }
                        }
                        // Strategy 6: aria-label, placeholder, name
                        if (!label) label = el.getAttribute('aria-label') || el.placeholder || el.name || '';
                        
                        label = label.replace(/\s*\*\s*$/, '').replace(/\n/g, ' ').trim();
                        results.push({
                            index: idx,
                            label: label,
                            value: el.value || '',
                            type: el.type || el.tagName.toLowerCase()
                        });
                    });
                    return results;
                })()
                ''')
            except Exception as e:
                add_log("FILL_GEM", f"Erreur scan JS (tentative {scan_attempt+1}): {str(e)[:80]}", "WARNING")
                scan_result = []

            # Check if we got labels
            labels_found = any(f.get('label', '') for f in scan_result)
            if labels_found:
                add_log("FILL_GEM", f"Scan réussi (tentative {scan_attempt+1}): {len(scan_result)} champs avec labels.", "SUCCESS")
                break
            elif scan_result:
                add_log("FILL_GEM", f"Tentative {scan_attempt+1}: {len(scan_result)} champs trouvés mais labels vides. Attente 3s...", "INFO")
                time.sleep(3)
            else:
                time.sleep(2)

        # Get element handles for filling
        input_elements = form_ctx.query_selector_all(
            "input:not([type='hidden']):not([type='file']):not([type='radio']):not([type='checkbox']), textarea"
        )
        radio_elements = form_ctx.query_selector_all("input[type='radio']")

        add_log("FILL_GEM", f"Trouvé {len(input_elements)} inputs, {len(radio_elements)} radios.", "SUCCESS")
        for f in scan_result:
            add_log("FILL_GEM", f"  → #{f['index']}: label='{f.get('label','')[:50]}' val='{f.get('value','')[:15]}'", "INFO")

        # ══════════════════════════════════════════════════════════
        # PHASE 2: Fill fields — with positional fallback for Gem
        # ══════════════════════════════════════════════════════════
        add_log("FILL_GEM", "Phase 2: Remplissage des champs...", "INFO")

        # Gem standard field order (always the same for basic Gem forms):
        # 0=First name, 1=Last name, 2=Email, 3=LinkedIn URL, 4+=custom
        GEM_POSITIONAL_MAP = [
            ("First name", first_name),
            ("Last name", last_name),
            ("Email", email_to_use),
            ("LinkedIn URL", linkedin_url),
        ]

        def _fill_element(el, value, label, add_log):
            """Fill a form element using Playwright's native methods."""
            try:
                el.click(timeout=2000)
                time.sleep(0.2)
                el.fill(value, timeout=3000)
                time.sleep(0.15)
                return True
            except Exception:
                try:
                    el.click(click_count=3, timeout=2000)
                    time.sleep(0.1)
                    el.type(value, delay=10, timeout=5000)
                    return True
                except Exception as e2:
                    add_log("FILL_GEM", f"⚠️ Échec remplissage '{label}': {str(e2)[:60]}", "WARNING")
                    return False

        if labels_found:
            # ── STRATEGY A: Labels available → use label-based mapping ──
            add_log("FILL_GEM", "Stratégie A: Remplissage par labels.", "INFO")
            for field_info in scan_result:
                idx = field_info['index']
                label = field_info['label']
                if field_info['value'].strip() or idx >= len(input_elements) or not label:
                    continue

                el = input_elements[idx]
                label_lower = label.lower()
                value = None

                if 'first name' in label_lower or 'prénom' in label_lower:
                    value = first_name
                elif 'last name' in label_lower or 'nom de famille' in label_lower:
                    value = last_name
                elif 'email' in label_lower:
                    value = email_to_use
                elif 'linkedin' in label_lower:
                    value = linkedin_url
                elif 'phone' in label_lower or 'téléphone' in label_lower:
                    value = phone_to_use
                elif 'github' in label_lower or 'portfolio' in label_lower or 'relevant link' in label_lower:
                    value = github_url
                elif 'salary' in label_lower or 'salaire' in label_lower or 'compensation' in label_lower or 'expectation' in label_lower:
                    value = salary_expectation or self.ask_llm(label, cv_text, cover_letter)
                else:
                    value = self.ask_llm(label, cv_text, cover_letter)

                if not value or value.lower() in ("none", "n/a", ""):
                    continue

                add_log("FILL_GEM", f"Remplissage '{label[:40]}' → '{str(value)[:40]}'", "INFO")
                if _fill_element(el, value, label, add_log):
                    fields_filled += 1

        else:
            # ── STRATEGY B: No labels → use Gem positional order fallback ──
            add_log("FILL_GEM", "Stratégie B: Labels vides → remplissage positionnel Gem.", "WARNING")

            for idx, el in enumerate(input_elements):
                # Check if field is already filled
                try:
                    current = el.evaluate("e => e.value") or ""
                    if current.strip():
                        continue
                except Exception:
                    pass

                value = None
                label = f"field_{idx}"

                if idx < len(GEM_POSITIONAL_MAP):
                    # Known standard Gem field
                    label, value = GEM_POSITIONAL_MAP[idx]
                else:
                    # Fields beyond standard 4 → try to determine by input type/context
                    input_type = ""
                    try:
                        input_type = el.evaluate("e => e.type || ''") or ""
                    except Exception:
                        pass

                    if input_type == "tel":
                        label = "Phone"
                        value = phone_to_use
                    elif input_type == "url":
                        label = "URL"
                        value = github_url or linkedin_url
                    elif input_type == "email":
                        label = "Email"
                        value = email_to_use
                    else:
                        # Get any context clue from placeholder
                        placeholder = ""
                        try:
                            placeholder = el.evaluate("e => e.placeholder || ''") or ""
                        except Exception:
                            pass

                        if placeholder:
                            label = placeholder
                            pl = placeholder.lower()
                            if 'phone' in pl:
                                value = phone_to_use
                            elif 'salary' in pl or 'compensation' in pl:
                                value = salary_expectation or self.ask_llm(placeholder, cv_text, cover_letter)
                            elif 'github' in pl or 'portfolio' in pl:
                                value = github_url
                            else:
                                value = self.ask_llm(placeholder, cv_text, cover_letter)
                        else:
                            # Absolute last resort: ask LLM with field position context
                            tag = "textarea" if idx >= 4 else "input"
                            try:
                                tag = el.evaluate("e => e.tagName.toLowerCase()") or tag
                            except Exception:
                                pass

                            if tag == "textarea":
                                label = "Custom question (textarea)"
                                value = self.ask_llm(
                                    "Why are you a strong fit for this role?",
                                    cv_text, cover_letter
                                )
                            else:
                                # Try common Gem patterns by position after the standard 4
                                custom_idx = idx - len(GEM_POSITIONAL_MAP)
                                common_extras = [
                                    ("Phone", phone_to_use),
                                    ("Salary expectations", salary_expectation or self.ask_llm("salary expectations", cv_text, cover_letter)),
                                    ("Portfolio/GitHub", github_url),
                                ]
                                if custom_idx < len(common_extras):
                                    label, value = common_extras[custom_idx]
                                else:
                                    label = f"Unknown field #{idx}"
                                    value = self.ask_llm(f"Application form field #{idx+1}", cv_text, cover_letter)

                if not value or value.lower() in ("none", "n/a", ""):
                    continue

                add_log("FILL_GEM", f"[Positionnel] '{label[:40]}' → '{str(value)[:40]}'", "INFO")
                if _fill_element(el, value, label, add_log):
                    fields_filled += 1


        # ══════════════════════════════════════════════════════════
        # PHASE 3: Handle radio buttons
        # ══════════════════════════════════════════════════════════
        add_log("FILL_GEM", "Phase 3: Traitement des boutons radio...", "INFO")

        # Group radios by name
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
                    const container = r.closest('fieldset') || r.closest('[class*="question"]') || r.closest('[class*="group"]');
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
                name = info['name']
                if name not in radio_groups:
                    radio_groups[name] = {'question': info['question'], 'options': []}
                radio_groups[name]['options'].append({'label': info['optLabel'], 'element': radio})
                if info['question'] and not radio_groups[name]['question']:
                    radio_groups[name]['question'] = info['question']
            except Exception:
                continue

        for group_name, group_data in radio_groups.items():
            question = group_data['question']
            option_labels = [opt['label'] for opt in group_data['options'] if opt['label']]
            if not option_labels or not question:
                continue

            chosen = self.ask_llm_choose_option(question, option_labels, cv_text)
            add_log("FILL_GEM", f"Radio '{question[:50]}' → IA choisit : '{chosen}'", "INFO")

            for opt in group_data['options']:
                if chosen.lower() in opt['label'].lower() or opt['label'].lower() in chosen.lower():
                    try:
                        opt['element'].click(force=True, timeout=3000)
                        fields_filled += 1
                        add_log("FILL_GEM", f"✅ Radio cliqué : '{opt['label']}'", "SUCCESS")
                    except Exception as e:
                        add_log("FILL_GEM", f"⚠️ Erreur clic radio: {str(e)[:60]}", "WARNING")
                    break

        # ══════════════════════════════════════════════════════════
        # PHASE 4: CV upload
        # ══════════════════════════════════════════════════════════
        add_log("FILL_GEM", "Phase 4: Upload du CV...", "INFO")
        try:
            file_el = form_ctx.query_selector("input[type='file']")
            if file_el and cv and cv.raw_file_url and not cv.raw_file_url.startswith("http"):
                abs_cv_path = f"/app/{cv.raw_file_url}"
                if os.path.exists(abs_cv_path):
                    file_el.set_input_files(abs_cv_path)
                    fields_filled += 1
                    add_log("FILL_GEM", f"✅ CV uploadé : {cv.filename}", "SUCCESS")
        except Exception as e:
            add_log("FILL_GEM", f"⚠️ Échec upload CV : {str(e)}", "WARNING")

        # Small pause to let React process all input events
        time.sleep(1)

        add_log("FILL_GEM", f"Remplissage terminé : {fields_filled} champ(s) rempli(s).", "SUCCESS" if fields_filled > 0 else "WARNING")
        return {"success": fields_filled > 0, "pending_questions": []}

    # ──────────────────────────────────────────────────────────────
    # Submit form
    # ──────────────────────────────────────────────────────────────
    def submit_form(self, page, add_log) -> bool:
        # Locate the specific Gem form context (iframe or page)
        form_ctx = self._get_form_context(page, add_log)

        submit_selectors = [
            "button[type='submit']",
            "button:has-text('Submit Application')",
            "button:has-text('Submit application')",
            "button:has-text('Submit')",
            "input[type='submit']",
            "button:has-text('Apply')",  # Safe inside iframe context
        ]

        for sel in submit_selectors:
            try:
                btn = form_ctx.query_selector(sel)
                if btn:
                    try:
                        btn.scroll_into_view_if_needed()
                    except Exception:
                        pass

                    add_log("SUBMIT_GEM", f"Bouton de soumission Gem trouvé ({sel}). Clic...", "INFO")
                    btn.click(force=True, timeout=5000)
                    time.sleep(4)
                    return True
            except Exception:
                pass
        return False
