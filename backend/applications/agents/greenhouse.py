import re
import time
import os
from typing import List, Any, Dict, Optional
from applications.agents.base import BasePlatformAgent


class GreenhouseAgent(BasePlatformAgent):
    """
    Agent specialized in handling Greenhouse job boards (boards.greenhouse.io).
    Uses AI (Groq LLM) to intelligently fill ALL form fields including:
    - Standard fields (name, email, phone, LinkedIn)
    - Custom text questions
    - Select dropdowns (work authorization, sponsorship, etc.)
    - Radio buttons
    - Cover letter / Resume upload
    """

    def detect(self, page, url: str) -> bool:
        url_lower = url.lower()
        if "greenhouse.io" in url_lower:
            return True
        try:
            if page.query_selector("#job_application_form"):
                return True
            for frame in page.frames:
                if "greenhouse.io" in (frame.url or "").lower():
                    return True
        except Exception:
            pass
        return False

    def _get_form_context(self, page, add_log):
        """Find the correct context (iframe or main page) for the Greenhouse form."""
        for frame in page.frames:
            if "greenhouse.io" in (frame.url or "").lower():
                add_log("FILL_GREENHOUSE", f"Formulaire Greenhouse trouvé dans l'iframe : {frame.url}", "SUCCESS")
                return frame
        if page.query_selector("#job_application_form"):
            add_log("FILL_GREENHOUSE", "Formulaire Greenhouse inline détecté.", "SUCCESS")
            return page
        add_log("FILL_GREENHOUSE", "Aucun formulaire Greenhouse détecté. Utilisation de la page principale.", "WARNING")
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
        add_log("FILL_GREENHOUSE", "Début du remplissage intelligent du formulaire Greenhouse...", "INFO")
        form_ctx = self._get_form_context(page, add_log)

        # ── Wait for form to fully render ──
        time.sleep(2)
        for attempt in range(8):
            try:
                test = form_ctx.query_selector("input:not([type='hidden']), textarea, select")
                if test:
                    break
            except Exception:
                pass
            time.sleep(1)

        # ── Extract candidate data ──
        full_name = personal_info.full_name if personal_info else "Candidat"
        first_name, last_name = "", ""
        if " " in full_name:
            first_name, last_name = full_name.split(" ", 1)
        else:
            first_name = full_name
            last_name = "Candidat"

        email_to_use = personal_info.email if personal_info else ""
        phone_to_use = personal_info.phone if personal_info else ""
        linkedin_url = getattr(personal_info, "linkedin_url", "") or ""
        github_url = getattr(personal_info, "github_url", "") or ""
        salary_expectation = getattr(personal_info, "salary_expectation", "") or ""

        cv_text = self.get_cv_text(cv)
        if not linkedin_url and cv_text:
            linkedin_url = self.extract_linkedin(cv_text)
        if not github_url and cv_text:
            github_url = self.extract_github(cv_text)

        fields_filled = 0
        pending_questions = []

        # ══════════════════════════════════════════════════════════
        # PHASE 1: Scan all form fields via JavaScript
        # ══════════════════════════════════════════════════════════
        add_log("FILL_GREENHOUSE", "Phase 1: Scanning des champs du formulaire...", "INFO")

        try:
            scan_result = form_ctx.evaluate(r'''
            (() => {
                const results = [];
                const inputs = document.querySelectorAll(
                    'input:not([type="hidden"]):not([type="file"]):not([type="radio"]):not([type="checkbox"]), textarea, select'
                );
                inputs.forEach((el, idx) => {
                    // Skip invisible/hidden elements
                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden' || 
                        el.getAttribute('aria-hidden') === 'true' ||
                        (el.offsetWidth === 0 && el.offsetHeight === 0)) {
                        return;
                    }
                    
                    // Skip captcha elements
                    const nameAttr = el.name || '';
                    const idAttr = el.id || '';
                    if (nameAttr.includes('recaptcha') || idAttr.includes('recaptcha') ||
                        nameAttr.includes('captcha') || idAttr.includes('captcha')) {
                        return;
                    }

                    let label = '';
                    if (el.id) {
                        const lbl = document.querySelector('label[for="' + el.id + '"]');
                        if (lbl) label = lbl.textContent.trim();
                    }
                    if (!label) {
                        const p = el.closest('label');
                        if (p) label = p.textContent.trim();
                    }
                    if (!label) {
                        const c = el.closest('.field') || el.closest('.field-wrapper') || el.parentElement;
                        if (c) {
                            const l = c.querySelector('label, span, p');
                            if (l && l !== el) label = l.textContent.trim();
                        }
                    }
                    if (!label) label = el.getAttribute('aria-label') || el.placeholder || el.name || '';

                    label = label.replace(/\s*\*\s*$/, '').replace(/\n/g, ' ').trim();

                    let options = [];
                    if (el.tagName.toLowerCase() === 'select') {
                        Array.from(el.options).forEach(opt => {
                            if (opt.value && opt.value !== '') {
                                options.push({ label: opt.textContent.trim(), value: opt.value });
                            }
                        });
                    }
                    
                    // Check if this is an autocomplete/combobox
                    const role = el.getAttribute('role') || '';
                    const autocomplete = el.getAttribute('autocomplete') || '';
                    const isAutocomplete = role === 'combobox' || el.getAttribute('aria-autocomplete') != null ||
                                           el.classList.contains('select__input') || el.classList.contains('ss-search');

                    results.push({
                        index: results.length,
                        domIndex: idx,
                        label: label,
                        value: el.value || '',
                        tag: el.tagName.toLowerCase(),
                        type: el.type || '',
                        name: nameAttr,
                        options: options,
                        isAutocomplete: isAutocomplete
                    });
                });
                return results;
            })()
            ''')
        except Exception as e:
            add_log("FILL_GREENHOUSE", f"Erreur scan JS: {str(e)[:80]}", "WARNING")
            scan_result = []

        add_log("FILL_GREENHOUSE", f"Trouvé {len(scan_result)} champs visibles.", "SUCCESS")
        for f in scan_result:
            add_log("FILL_GREENHOUSE", f"  → #{f['index']}: tag={f['tag']} label='{f.get('label','')[:40]}' auto={f.get('isAutocomplete', False)}", "INFO")

        # Get VISIBLE element handles (must match the JS filter)
        visible_elements = form_ctx.evaluate(r'''
        (() => {
            const indices = [];
            const inputs = document.querySelectorAll(
                'input:not([type="hidden"]):not([type="file"]):not([type="radio"]):not([type="checkbox"]), textarea, select'
            );
            inputs.forEach((el, idx) => {
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' ||
                    el.getAttribute('aria-hidden') === 'true' ||
                    (el.offsetWidth === 0 && el.offsetHeight === 0)) return;
                const nameAttr = el.name || '';
                const idAttr = el.id || '';
                if (nameAttr.includes('recaptcha') || idAttr.includes('recaptcha') ||
                    nameAttr.includes('captcha') || idAttr.includes('captcha')) return;
                indices.push(idx);
            });
            return indices;
        })()
        ''')
        
        # Get all elements then filter to visible ones
        all_elements = form_ctx.query_selector_all(
            "input:not([type='hidden']):not([type='file']):not([type='radio']):not([type='checkbox']), textarea, select"
        )
        input_elements = [all_elements[i] for i in visible_elements if i < len(all_elements)]

        # ══════════════════════════════════════════════════════════
        # PHASE 2: Map labels to values and fill
        # ══════════════════════════════════════════════════════════
        add_log("FILL_GREENHOUSE", "Phase 2: Remplissage des champs...", "INFO")

        filled_labels = set()  # Track labels we've already filled to skip duplicates

        for field_info in scan_result:
            idx = field_info['index']
            label = field_info['label']
            tag = field_info['tag']
            options = field_info.get('options', [])
            is_autocomplete = field_info.get('isAutocomplete', False)
            field_name = field_info.get('name', '')

            if idx >= len(input_elements):
                continue

            el = input_elements[idx]
            label_lower = label.lower()

            # Skip pure search helper inputs (no label = just a search box)
            if label_lower == 'search' or field_name == 'search':
                continue

            # Skip duplicate labels (Greenhouse renders some custom fields with 2 inputs)
            if label_lower in filled_labels and label_lower:
                add_log("FILL_GREENHOUSE", f"  Skip duplicate: '{label[:30]}'", "INFO")
                continue

            # ── Handle AUTOCOMPLETE/COMBOBOX fields (Country, City, Yes/No dropdowns) ──
            if is_autocomplete:
                value = None
                # Check if user provided an answer
                field_id = self._get_field_id(el)
                if user_responses and field_id in user_responses:
                    value = user_responses[field_id]
                    add_log("FILL_GREENHOUSE", f"✅ Utilisation de la réponse utilisateur pour : {field_id}", "SUCCESS")
                else:
                    if 'country' in label_lower:
                        value = "Tunisia"
                    elif 'location' in label_lower or 'city' in label_lower:
                        value = "Tunis"
                    elif any(w in label_lower for w in ['privacy', 'notice', 'consent', 'policy', 'terms', 'rgpd', 'gdpr', 'read and understood']):
                        value = "I confirm"
                    elif 'authoris' in label_lower or 'authorized' in label_lower or 'work permit' in label_lower:
                        value = self.ask_llm(label, cv_text, cover_letter)
                    elif 'available' in label_lower or 'office' in label_lower:
                        value = self.ask_llm(label, cv_text, cover_letter)
                    else:
                        value = self.ask_llm(label, cv_text, cover_letter)

                if not value or value.lower() in ("none", "n/a", ""):
                    # Check if this is an important field that needs user input
                    is_required = self._is_field_required(el)
                    important_keywords = ["country", "location", "city", "authoris", "authorized", "work permit", "available", "office"]
                    if is_required or any(keyword in label_lower for keyword in important_keywords):
                        pending_questions.append(self._build_pending_question(field_id, label, "text", is_required))
                        add_log("FILL_GREENHOUSE", f"⚠️ Question en attente : {label}", "WARNING")
                    continue

                option_clicked = False

                # 1. Attempt to reveal options via ArrowDown (standard React-Select behavior)
                if 'country' not in label_lower:
                    try:
                        el.focus()
                        form_ctx.keyboard.press("ArrowDown")
                        time.sleep(0.3)
                        opts = form_ctx.query_selector_all(".select__option, div[role='option'], li[role='option']")
                        visible_opts = [o for o in opts if o.is_visible()]
                        if visible_opts:
                            target_opt = None
                            if any(w in label_lower for w in ['privacy', 'notice', 'consent', 'policy', 'terms', 'read and understood']):
                                for o in visible_opts:
                                    ot = o.inner_text().lower()
                                    if any(w in ot for w in ['confirm', 'agree', 'yes', 'read', 'accept', 'understood']):
                                        target_opt = o
                                        break
                                if not target_opt and len(visible_opts) == 1:
                                    target_opt = visible_opts[0]
                            elif value:
                                val_lower = str(value).lower().strip()
                                for o in visible_opts:
                                    ot = o.inner_text().lower().strip()
                                    if val_lower == ot or val_lower in ot or ot in val_lower:
                                        target_opt = o
                                        break

                            if target_opt:
                                target_opt.click(timeout=1500)
                                option_clicked = True
                                fields_filled += 1
                                filled_labels.add(label_lower)
                                add_log("FILL_GREENHOUSE", f"Select '{label[:30]}' → '{target_opt.inner_text().strip()}'", "SUCCESS")
                            else:
                                form_ctx.keyboard.press("Escape")
                    except Exception:
                        pass

                # 2. If ArrowDown didn't select an option, fallback to type-to-search
                if not option_clicked:
                    try:
                        # Click → clear → type to trigger the dropdown
                        el.click(timeout=2000)
                        time.sleep(0.3)
                        el.fill("", timeout=1000)  # Clear existing
                        time.sleep(0.2)
                        el.type(value, delay=50, timeout=5000)
                        time.sleep(1)  # Wait for dropdown options to appear

                        # Try to click the first visible dropdown option
                        option_selectors = [
                            f"div[role='option']", "li[role='option']",
                            ".ss-option", ".select__option",
                            "div.option", "ul.options li",
                            "[class*='option']:not([class*='hidden'])"
                        ]
                        for opt_sel in option_selectors:
                            try:
                                opts = form_ctx.query_selector_all(opt_sel)
                                for opt in opts:
                                    try:
                                        if opt.is_visible():
                                            opt.click(timeout=1000)
                                            option_clicked = True
                                            break
                                    except Exception:
                                        continue
                                if option_clicked:
                                    break
                            except Exception:
                                continue

                        fields_filled += 1
                        filled_labels.add(label_lower)
                        if option_clicked:
                            add_log("FILL_GREENHOUSE", f"Autocomplete '{label[:30]}' → '{value}' (option cliquée)", "SUCCESS")
                        else:
                            add_log("FILL_GREENHOUSE", f"Autocomplete '{label[:30]}' → '{value}' (tapé)", "SUCCESS")
                    except Exception as ac_err:
                        add_log("FILL_GREENHOUSE", f"Erreur autocomplete '{label[:30]}': {str(ac_err)[:50]}", "WARNING")
                continue

            # Skip already filled fields
            try:
                current_val = el.evaluate("e => e.value") or ""
                if current_val.strip() and current_val != "0" and current_val != "-1":
                    continue
            except Exception:
                pass

            # ── Handle SELECT dropdowns ──
            if tag == "select" and options:
                opt_labels = [o['label'] for o in options]
                
                # Check if user provided an answer
                field_id = self._get_field_id(el)
                if user_responses and field_id in user_responses:
                    chosen = user_responses[field_id]
                    add_log("FILL_GREENHOUSE", f"✅ Utilisation de la réponse utilisateur pour : {field_id}", "SUCCESS")
                else:
                    chosen = self.ask_llm_choose_option(label or "Select an option", opt_labels, cv_text)

                target_val = None
                for o in options:
                    if chosen.lower() in o['label'].lower() or o['label'].lower() in chosen.lower():
                        target_val = o['value']
                        break

                if target_val:
                    try:
                        el.select_option(target_val)
                        fields_filled += 1
                        filled_labels.add(label_lower)
                        add_log("FILL_GREENHOUSE", f"Dropdown '{label[:30]}' → '{chosen}'", "SUCCESS")
                    except Exception as se:
                        add_log("FILL_GREENHOUSE", f"Erreur select '{label}': {str(se)[:50]}", "WARNING")
                else:
                    # Check if this is a required field that needs user input
                    is_required = self._is_field_required(el)
                    if is_required:
                        pending_questions.append(self._build_pending_question(field_id, label, "select", is_required, opt_labels))
                        add_log("FILL_GREENHOUSE", f"⚠️ Question en attente : {label}", "WARNING")
                continue

            # ── Handle TEXT inputs and TEXTAREAS ──
            value = None
            
            # Check if user provided an answer
            field_id = self._get_field_id(el)
            if user_responses and field_id in user_responses:
                value = user_responses[field_id]
                add_log("FILL_GREENHOUSE", f"✅ Utilisation de la réponse utilisateur pour : {field_id}", "SUCCESS")
            else:
                if 'first name' in label_lower or 'prénom' in label_lower or 'first_name' in label_lower:
                    value = first_name
                elif 'last name' in label_lower or 'nom de famille' in label_lower or 'last_name' in label_lower:
                    value = last_name
                elif 'email' in label_lower:
                    value = email_to_use
                elif 'phone' in label_lower or 'téléphone' in label_lower:
                    value = phone_to_use
                elif 'linkedin' in label_lower:
                    value = linkedin_url
                elif 'github' in label_lower or 'portfolio' in label_lower or 'website' in label_lower or 'relevant link' in label_lower:
                    value = github_url
                elif 'salary' in label_lower or 'salaire' in label_lower or 'compensation' in label_lower or 'expectation' in label_lower:
                    value = salary_expectation or self.ask_llm(label, cv_text, cover_letter)
                elif 'cover letter' in label_lower or 'lettre de motivation' in label_lower:
                    value = cover_letter
                elif label:
                    value = self.ask_llm(label, cv_text, cover_letter)

            if not value or value.lower() in ("none", "n/a", ""):
                # Check if this is an important/required field that needs user input
                is_required = self._is_field_required(el)
                important_keywords = ["linkedin", "github", "portfolio", "website", "salary", "salaire", "compensation", "expectation", "why", "motivation", "cover letter", "lettre de motivation"]
                # Long textareas are usually important questions
                is_textarea = tag == "textarea"
                
                if is_required or any(keyword in label_lower for keyword in important_keywords) or is_textarea:
                    field_type = "textarea" if is_textarea else "text"
                    pending_questions.append(self._build_pending_question(field_id, label, field_type, is_required))
                    add_log("FILL_GREENHOUSE", f"⚠️ Question en attente : {label}", "WARNING")
                continue

            try:
                el.click(timeout=2000)
                time.sleep(0.15)
                el.fill(value, timeout=3000)
                fields_filled += 1
                filled_labels.add(label_lower)
                add_log("FILL_GREENHOUSE", f"Texte '{label[:30]}' → '{str(value)[:30]}'", "SUCCESS")
            except Exception:
                try:
                    el.click(click_count=3, timeout=2000)
                    time.sleep(0.1)
                    el.type(value, delay=10, timeout=5000)
                    fields_filled += 1
                    filled_labels.add(label_lower)
                except Exception as fe:
                    add_log("FILL_GREENHOUSE", f"Erreur saisie '{label}': {str(fe)[:50]}", "WARNING")

        # ══════════════════════════════════════════════════════════
        # PHASE 3: Handle radio button groups
        # ══════════════════════════════════════════════════════════
        add_log("FILL_GREENHOUSE", "Phase 3: Traitement des boutons radio...", "INFO")
        try:
            radio_elements = form_ctx.query_selector_all("input[type='radio']")
            radio_groups = {}
            for radio in radio_elements:
                try:
                    name = radio.get_attribute("name")
                    if not name:
                        continue
                    if name not in radio_groups:
                        radio_groups[name] = {"question": "", "options": []}

                    # Get radio option label
                    opt_label = ""
                    radio_id = radio.get_attribute("id")
                    if radio_id:
                        lbl_el = form_ctx.query_selector(f"label[for='{radio_id}']")
                        if lbl_el:
                            opt_label = lbl_el.inner_text().strip()
                    if not opt_label:
                        opt_label = radio.evaluate("e => e.closest('label')?.textContent?.trim() || ''") or ""

                    radio_groups[name]["options"].append({"label": opt_label, "element": radio})

                    # Get the group question label
                    if not radio_groups[name]["question"]:
                        q = radio.evaluate(r'''e => {
                            const container = e.closest('.field') || e.closest('fieldset') || e.parentElement?.parentElement;
                            if (container) {
                                const lbl = container.querySelector('label, span, legend, p');
                                if (lbl) return lbl.textContent.trim();
                            }
                            return '';
                        }''') or ""
                        radio_groups[name]["question"] = re.sub(r'\s*\*\s*$', '', q).strip()
                except Exception:
                    continue

            for name, group in radio_groups.items():
                question = group["question"]
                options = group["options"]
                if not question or not options:
                    continue

                opt_labels = [opt["label"] for opt in options if opt["label"]]
                if not opt_labels:
                    continue

                # Check if user provided an answer
                field_id = question.lower().replace(" ", "_").replace("?", "")
                if user_responses and field_id in user_responses:
                    chosen = user_responses[field_id]
                    add_log("FILL_GREENHOUSE", f"✅ Utilisation de la réponse utilisateur pour : {field_id}", "SUCCESS")
                else:
                    chosen = self.ask_llm_choose_option(question, opt_labels, cv_text)

                for opt in options:
                    if chosen.lower() in opt["label"].lower() or opt["label"].lower() in chosen.lower():
                        try:
                            opt["element"].click(timeout=2000)
                            fields_filled += 1
                            add_log("FILL_GREENHOUSE", f"Radio '{question[:30]}' → '{opt['label']}'", "SUCCESS")
                            break
                        except Exception:
                            pass
                
                # If we couldn't fill this radio group, check if it's important
                if not any(chosen.lower() in opt["label"].lower() or opt["label"].lower() in chosen.lower() for opt in options):
                    is_required = self._is_radio_group_required(form_ctx, question)
                    important_keywords = ["sponsorship", "visa", "work authorization", "authoris", "authorized", "work permit"]
                    if is_required or any(keyword in question.lower() for keyword in important_keywords):
                        pending_questions.append(self._build_pending_question(field_id, question, "radio", is_required, opt_labels))
                        add_log("FILL_GREENHOUSE", f"⚠️ Question en attente : {question}", "WARNING")
        except Exception as radio_err:
            add_log("FILL_GREENHOUSE", f"Erreur boutons radio: {str(radio_err)[:80]}", "WARNING")

        # ══════════════════════════════════════════════════════════
        # PHASE 4: Upload Resume/CV file
        # ══════════════════════════════════════════════════════════
        add_log("FILL_GREENHOUSE", "Phase 4: Upload du CV...", "INFO")
        try:
            resume_input = form_ctx.query_selector(
                "input[type='file'][name*='resume'], input[type='file']#resume, "
                "input[type='file'][name*='cv'], input[type='file']"
            )
            if resume_input:
                cv_path = cv.raw_file_url
                if cv_path and not cv_path.startswith("http"):
                    abs_cv_path = f"/app/{cv_path}" if not os.path.exists(cv_path) else cv_path
                    if os.path.exists(abs_cv_path):
                        resume_input.set_input_files(abs_cv_path)
                        try:
                            resume_input.evaluate("el => { el.dispatchEvent(new Event('change', { bubbles: true })); el.dispatchEvent(new Event('input', { bubbles: true })); }")
                        except Exception:
                            pass
                        time.sleep(3)  # Allow Greenhouse client-side S3 upload to finish
                        fields_filled += 1
                        add_log("FILL_GREENHOUSE", f"CV téléchargé : {cv.filename}", "SUCCESS")
        except Exception as e:
            add_log("FILL_GREENHOUSE", f"Échec de l'upload du CV : {str(e)}", "WARNING")
        # ══════════════════════════════════════════════════════════
        # PHASE 5: Handle checkboxes (GDPR, consent, required)
        # ══════════════════════════════════════════════════════════
        add_log("FILL_GREENHOUSE", "Phase 5: Traitement des cases à cocher...", "INFO")
        try:
            checkbox_elements = form_ctx.query_selector_all("input[type='checkbox']")
            for cb in checkbox_elements:
                try:
                    cb_id = cb.get_attribute("id")
                    cb_name = cb.get_attribute("name") or ""
                    cb_label = ""
                    if cb_id:
                        lbl_el = form_ctx.query_selector(f"label[for='{cb_id}']")
                        if lbl_el:
                            cb_label = lbl_el.inner_text().strip()
                    if not cb_label:
                        cb_label = cb.evaluate("e => e.closest('label')?.textContent?.trim() || ''") or ""
                    
                    is_required = cb.evaluate("e => e.required || e.getAttribute('aria-required') === 'true'")
                    cb_label_lower = cb_label.lower()
                    
                    consent_words = ["consent", "privacy", "data", "processing", "policy", "terms", "agree", 
                                     "read", "understand", "accept", "rgpd", "gdpr", "condition", "accord", 
                                     "autorise", "donnée", "traitement"]
                    
                    should_check = is_required or any(w in cb_label_lower for w in consent_words) or any(w in cb_name.lower() for w in consent_words)
                    
                    is_checked = cb.evaluate("e => e.checked")
                    if should_check and not is_checked:
                        cb.click(timeout=2000)
                        fields_filled += 1
                        add_log("FILL_GREENHOUSE", f"Checkbox coché : '{cb_label[:30]}' (name={cb_name[:20]})", "SUCCESS")
                except Exception:
                    pass
        except Exception as cb_err:
            add_log("FILL_GREENHOUSE", f"Erreur cases à cocher: {str(cb_err)[:80]}", "WARNING")

        add_log("FILL_GREENHOUSE", f"Remplissage terminé : {fields_filled} champ(s) rempli(s).", "SUCCESS")
        return {"success": fields_filled > 0, "pending_questions": pending_questions}

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

    def _is_radio_group_required(self, form_ctx, question_text: str) -> bool:
        """Check if a radio button group is required."""
        try:
            radio_elements = form_ctx.query_selector_all("input[type='radio']")
            for radio in radio_elements:
                if self._is_field_required(radio):
                    return True
            return False
        except Exception:
            return False

    def submit_form(self, page, add_log) -> bool:
        try:
            form_ctx = self._get_form_context(page, add_log)
            submit_btn = form_ctx.query_selector(
                "input[type='submit']#submit_app, button#submit_app, "
                "input[type='submit']#submit_button, button#submit_button, "
                "input[type='submit'], button[type='submit']"
            )
            if submit_btn:
                submit_btn.click()
                add_log("SUBMIT_GREENHOUSE", "Bouton de soumission cliqué.", "SUCCESS")
                time.sleep(5)
                return True
            else:
                add_log("SUBMIT_GREENHOUSE", "Bouton de soumission non trouvé.", "WARNING")
        except Exception as e:
            add_log("SUBMIT_GREENHOUSE", f"Échec de la soumission : {str(e)}", "WARNING")
        return False
