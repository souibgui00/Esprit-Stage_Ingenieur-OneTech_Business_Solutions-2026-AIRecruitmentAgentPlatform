import re
import time
import os
from typing import List, Any, Dict, Optional
from applications.agents.base import BasePlatformAgent


class LeverAgent(BasePlatformAgent):
    """
    Agent specialized in handling Lever job boards (jobs.lever.co).
    Uses AI (Groq LLM) to intelligently fill ALL form fields including:
    - Standard fields (name, email, phone, LinkedIn)
    - Custom text questions
    - Cover letter / Resume upload
    """

    def detect(self, page, url: str) -> bool:
        url_lower = url.lower()
        if "lever.co" in url_lower:
            return True
        try:
            if page.query_selector(".application-form"):
                return True
            for frame in page.frames:
                if "lever.co" in (frame.url or "").lower():
                    return True
        except Exception:
            pass
        return False

    def _get_form_context(self, page, add_log):
        """Find the correct context (iframe or main page) for the Lever form."""
        for frame in page.frames:
            if "lever.co" in (frame.url or "").lower():
                add_log("FILL_LEVER", f"Formulaire Lever trouvé dans l'iframe : {frame.url}", "SUCCESS")
                return frame
        if page.query_selector(".application-form"):
            add_log("FILL_LEVER", "Formulaire Lever inline détecté.", "SUCCESS")
            return page
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
        add_log("FILL_LEVER", "Début du remplissage intelligent du formulaire Lever...", "INFO")
        form_ctx = self._get_form_context(page, add_log)

        # ── Wait for form to fully render ──
        time.sleep(2)
        for attempt in range(8):
            try:
                test = form_ctx.query_selector("input:not([type='hidden']), textarea")
                if test:
                    break
            except Exception:
                pass
            time.sleep(1)

        # ── Extract candidate data ──
        full_name = personal_info.full_name if personal_info else "Candidat"
        email_to_use = personal_info.email if personal_info else ""
        phone_to_use = personal_info.phone if personal_info else ""
        linkedin_url = getattr(personal_info, "linkedin_url", "") or ""
        github_url = getattr(personal_info, "github_url", "") or ""

        cv_text = self.get_cv_text(cv)
        if not linkedin_url and cv_text:
            linkedin_url = self.extract_linkedin(cv_text)
        if not github_url and cv_text:
            github_url = self.extract_github(cv_text)

        fields_filled = 0

        # ══════════════════════════════════════════════════════════
        # PHASE 1: Scan all form fields via JavaScript
        # ══════════════════════════════════════════════════════════
        add_log("FILL_LEVER", "Phase 1: Scanning des champs du formulaire...", "INFO")

        try:
            scan_result = form_ctx.evaluate(r'''
            (() => {
                const results = [];
                const inputs = document.querySelectorAll(
                    'input:not([type="hidden"]):not([type="file"]):not([type="radio"]):not([type="checkbox"]), textarea, select'
                );
                inputs.forEach((el, idx) => {
                    let label = '';
                    if (el.id) {
                        const lbl = document.querySelector('label[for="' + el.id + '"]');
                        if (lbl) label = lbl.textContent.trim();
                    }
                    if (!label && el.name) {
                        const lbl = document.querySelector('label[for="' + el.name + '"]');
                        if (lbl) label = lbl.textContent.trim();
                    }
                    if (!label) {
                        const p = el.closest('label');
                        if (p) label = p.textContent.trim();
                    }
                    if (!label) {
                        const c = el.closest('.application-question') || el.closest('.field') || el.parentElement;
                        if (c) {
                            const l = c.querySelector('label, .label, span, p');
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

                    results.push({
                        index: idx,
                        label: label,
                        value: el.value || '',
                        tag: el.tagName.toLowerCase(),
                        options: options
                    });
                });
                return results;
            })()
            ''')
        except Exception as e:
            add_log("FILL_LEVER", f"Erreur scan JS: {str(e)[:80]}", "WARNING")
            scan_result = []

        add_log("FILL_LEVER", f"Trouvé {len(scan_result)} champs.", "SUCCESS")
        for f in scan_result:
            add_log("FILL_LEVER", f"  → #{f['index']}: tag={f['tag']} label='{f.get('label','')[:40]}'", "INFO")

        input_elements = form_ctx.query_selector_all(
            "input:not([type='hidden']):not([type='file']):not([type='radio']):not([type='checkbox']), textarea, select"
        )

        # ══════════════════════════════════════════════════════════
        # PHASE 2: Map labels to values and fill
        # ══════════════════════════════════════════════════════════
        add_log("FILL_LEVER", "Phase 2: Remplissage des champs...", "INFO")

        for field_info in scan_result:
            idx = field_info['index']
            label = field_info['label']
            tag = field_info['tag']
            options = field_info.get('options', [])

            if idx >= len(input_elements):
                continue

            el = input_elements[idx]
            label_lower = label.lower()

            # Skip already filled
            try:
                current_val = el.evaluate("e => e.value") or ""
                if current_val.strip():
                    continue
            except Exception:
                pass

            # ── Handle SELECT dropdowns ──
            if tag == "select" and options:
                opt_labels = [o['label'] for o in options]
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
                        add_log("FILL_LEVER", f"Dropdown '{label[:30]}' → '{chosen}'", "SUCCESS")
                    except Exception as se:
                        add_log("FILL_LEVER", f"Erreur select: {str(se)[:50]}", "WARNING")
                continue

            # ── Handle TEXT inputs and TEXTAREAS ──
            value = None
            field_id = self._get_field_id(el)

            # 1. Check user_responses first
            if user_responses and field_id in user_responses:
                value = user_responses[field_id]
                add_log("FILL_LEVER", f"✅ Réponse utilisateur pour {field_id}: {value[:30]}", "SUCCESS")
            elif 'name' == label_lower or 'full name' in label_lower or 'nom' in label_lower:
                value = full_name
            elif 'email' in label_lower:
                value = email_to_use
            elif 'phone' in label_lower or 'téléphone' in label_lower:
                value = phone_to_use
            elif 'linkedin' in label_lower:
                value = linkedin_url
            elif 'github' in label_lower or 'portfolio' in label_lower or 'website' in label_lower:
                value = github_url
            elif any(kw in label_lower for kw in ['salary', 'salaire', 'gehalt', 'compensation', 'remuneration', 'vergütung']):
                salary_exp = getattr(personal_info, "salary_expectation", "") or ""
                value = salary_exp if salary_exp else None
            elif 'cover letter' in label_lower or 'lettre' in label_lower or 'comments' in label_lower:
                value = cover_letter
            elif label:
                # Don't hallucinate sensitive/availability/contract questions with arbitrary LLM text
                if not any(kw in label_lower for kw in ['verfügbar', 'availability', 'start date', 'gehalt', 'salary', 'kündigungsfrist', 'notice period']):
                    value = self.ask_llm(label, cv_text, cover_letter)

            if not value or value.lower() in ("none", "n/a", ""):
                continue


            try:
                el.click(timeout=2000)
                time.sleep(0.15)
                el.fill(value, timeout=3000)
                fields_filled += 1
                add_log("FILL_LEVER", f"Texte '{label[:30]}' → '{str(value)[:30]}'", "SUCCESS")
            except Exception as fe:
                add_log("FILL_LEVER", f"Erreur saisie '{label}': {str(fe)[:50]}", "WARNING")

        # ══════════════════════════════════════════════════════════
        # PHASE 3: Upload Resume/CV file
        # ══════════════════════════════════════════════════════════
        add_log("FILL_LEVER", "Phase 3: Upload du CV...", "INFO")
        try:
            resume_input = form_ctx.query_selector(
                "input[type='file'][name='resume'], input[type='file'][name*='cv'], input[type='file']"
            )
            if resume_input:
                cv_path = cv.raw_file_url
                if cv_path and not cv_path.startswith("http") and "/" in cv_path:
                    abs_cv_path = f"/app/{cv_path}"
                    if os.path.exists(abs_cv_path):
                        resume_input.set_input_files(abs_cv_path)
                        fields_filled += 1
                        add_log("FILL_LEVER", f"CV téléchargé : {cv.filename}", "SUCCESS")
                    else:
                        add_log("FILL_LEVER", f"Fichier CV introuvable : {abs_cv_path}", "WARNING")
            else:
                add_log("FILL_LEVER", "Aucun champ de fichier CV trouvé.", "WARNING")
        except Exception as e:
            add_log("FILL_LEVER", f"Échec de l'upload du CV : {str(e)}", "WARNING")


        # ══════════════════════════════════════════════════════════
        # PHASE 4: Collect pending questions for unfilled important fields
        # ══════════════════════════════════════════════════════════
        add_log("FILL_LEVER", "Phase 4: Collecte des questions en attente...", "INFO")
        pending_questions = []

        important_text_keywords = [
            "linkedin", "github", "portfolio", "website", "salary", "salaire", "gehalt",
            "compensation", "vergütung", "expectation", "vorstellung", "why", "motivation", "cover", "letter",
            "sponsorship", "visa", "work authorization", "contract", "verfügbar", "availability", "notice"
        ]


        # Scan all text/textarea fields that weren't filled
        try:
            all_inputs = form_ctx.query_selector_all(
                "input[type='text'], input[type='number'], input[type='url'], input:not([type])"
            )
            for inp in all_inputs:
                if not inp.is_visible():
                    continue
                try:
                    current_val = inp.evaluate("e => e.value") or ""
                    if current_val.strip():
                        continue
                except Exception:
                    pass
                is_required = self._is_field_required(inp)
                placeholder = inp.get_attribute("placeholder") or ""
                name_attr = inp.get_attribute("name") or ""
                id_attr = inp.get_attribute("id") or ""
                field_label = placeholder or name_attr or id_attr or ""
                label_lower = field_label.lower()
                field_id = self._get_field_id(inp)
                # Check user_responses first
                if user_responses and field_id in user_responses:
                    try:
                        inp.fill(user_responses[field_id])
                        fields_filled += 1
                        add_log("FILL_LEVER", f"✅ Réponse utilisateur pour : {field_id}", "SUCCESS")
                    except Exception:
                        pass
                    continue
                if is_required or any(kw in label_lower for kw in important_text_keywords):
                    pending_questions.append(
                        self._build_pending_question(field_id, field_label or "Information supplémentaire", "text", is_required)
                    )
                    add_log("FILL_LEVER", f"⚠️ Question en attente : {field_label}", "WARNING")
        except Exception as e:
            add_log("FILL_LEVER", f"⚠️ Erreur scan text inputs : {str(e)[:80]}", "WARNING")

        # Scan textareas
        try:
            all_textareas = form_ctx.query_selector_all("textarea")
            for ta in all_textareas:
                if not ta.is_visible():
                    continue
                try:
                    current_val = ta.evaluate("e => e.value") or ""
                    if current_val.strip():
                        continue
                except Exception:
                    pass
                is_required = self._is_field_required(ta)
                placeholder = ta.get_attribute("placeholder") or ""
                name_attr = ta.get_attribute("name") or ""
                # Try to get label from DOM context
                try:
                    ta_label = ta.evaluate(r"""el => {
                        if (el.id) { const l = document.querySelector('label[for="' + el.id + '"]'); if (l) return l.textContent.trim(); }
                        const p = el.closest('label'); if (p) return p.textContent.trim();
                        const c = el.closest('.application-question') || el.closest('.field') || el.parentElement;
                        if (c) { const l = c.querySelector('label, .label, span, p'); if (l && l !== el) return l.textContent.trim(); }
                        return '';
                    }""") or ""
                except Exception:
                    ta_label = ""
                field_label = ta_label or placeholder or name_attr or "Information supplémentaire"
                field_id = self._get_field_id(ta)
                # Check user_responses first
                if user_responses and field_id in user_responses:
                    try:
                        ta.fill(user_responses[field_id])
                        fields_filled += 1
                        add_log("FILL_LEVER", f"✅ Réponse utilisateur pour textarea : {field_id}", "SUCCESS")
                    except Exception:
                        pass
                    continue
                # Try LLM if we have CV text
                if cv_text:
                    answer = self.ask_llm(field_label, cv_text, cover_letter)
                    if answer and answer.lower() not in ("none", "n/a", ""):
                        try:
                            ta.fill(answer)
                            fields_filled += 1
                            add_log("FILL_LEVER", f"✅ 🤖 Textarea '{field_label[:30]}' rempli par IA.", "SUCCESS")
                            continue
                        except Exception:
                            pass
                pending_questions.append(
                    self._build_pending_question(field_id, field_label, "textarea", is_required)
                )
                add_log("FILL_LEVER", f"⚠️ Question textarea en attente : {field_label}", "WARNING")
        except Exception as e:
            add_log("FILL_LEVER", f"⚠️ Erreur scan textareas : {str(e)[:80]}", "WARNING")

        # Scan selects not yet filled
        try:
            all_selects = form_ctx.query_selector_all("select")
            for sel_el in all_selects:
                if not sel_el.is_visible():
                    continue
                try:
                    current_val = sel_el.evaluate("e => e.value") or ""
                    if current_val and current_val not in ("", "-1", "0"):
                        continue
                except Exception:
                    pass
                is_required = self._is_field_required(sel_el)
                if not is_required:
                    continue
                name_attr = sel_el.get_attribute("name") or sel_el.get_attribute("id") or "Dropdown"
                field_id = self._get_field_id(sel_el)
                options = [o.inner_text().strip() for o in sel_el.query_selector_all("option")
                           if o.inner_text().strip() and o.inner_text().strip() not in ["", "Select...", "Choose..."]]
                if user_responses and field_id in user_responses:
                    chosen = user_responses[field_id]
                    if chosen in options:
                        try:
                            sel_el.select_option(chosen)
                            fields_filled += 1
                            add_log("FILL_LEVER", f"✅ Réponse utilisateur pour select : {field_id}", "SUCCESS")
                        except Exception:
                            pass
                    continue
                pending_questions.append(
                    self._build_pending_question(field_id, name_attr, "select", is_required, options)
                )
                add_log("FILL_LEVER", f"⚠️ Select en attente : {name_attr}", "WARNING")
        except Exception as e:
            add_log("FILL_LEVER", f"⚠️ Erreur scan selects : {str(e)[:80]}", "WARNING")

        # Scan radio button groups
        try:
            radio_elements = form_ctx.query_selector_all("input[type='radio']")
            radio_groups = {}
            for radio in radio_elements:
                try:
                    name = radio.get_attribute("name")
                    if not name or name in radio_groups:
                        continue
                    # Get group question
                    question = radio.evaluate(r"""e => {
                        const c = e.closest('.application-question') || e.closest('fieldset') || e.parentElement?.parentElement;
                        if (c) { const l = c.querySelector('label, legend, span, p'); if (l) return l.textContent.trim(); }
                        return '';
                    }""") or name
                    import re as _re
                    question = _re.sub(r'\s*\*\s*$', '', question).strip()
                    # Collect options
                    group_radios = form_ctx.query_selector_all(f"input[type='radio'][name='{name}']")
                    opts = []
                    for gr in group_radios:
                        rid = gr.get_attribute("id")
                        opt_label = ""
                        if rid:
                            lbl_el = form_ctx.query_selector(f"label[for='{rid}']")
                            if lbl_el:
                                opt_label = lbl_el.inner_text().strip()
                        if not opt_label:
                            opt_label = gr.evaluate("e => e.closest('label')?.textContent?.trim() || ''") or ""
                        opts.append(opt_label)
                    radio_groups[name] = {"question": question, "options": opts}
                except Exception:
                    continue

            for name, group in radio_groups.items():
                question = group["question"]
                opts = [o for o in group["options"] if o]
                if not question or not opts:
                    continue
                field_id = question.lower().replace(" ", "_").replace("?", "")[:40]
                if user_responses and field_id in user_responses:
                    chosen = user_responses[field_id]
                    radios = form_ctx.query_selector_all(f"input[type='radio'][name='{name}']")
                    for gr in radios:
                        rid = gr.get_attribute("id")
                        opt_lbl = ""
                        if rid:
                            lbl_el = form_ctx.query_selector(f"label[for='{rid}']")
                            if lbl_el:
                                opt_lbl = lbl_el.inner_text().strip()
                        if chosen.lower() in opt_lbl.lower() or opt_lbl.lower() in chosen.lower():
                            try:
                                gr.click(timeout=2000)
                                fields_filled += 1
                                add_log("FILL_LEVER", f"✅ Radio '{question[:30]}' → '{opt_lbl}'", "SUCCESS")
                            except Exception:
                                pass
                            break
                    continue
                chosen = self.ask_llm_choose_option(question, opts, cv_text) if cv_text else ""
                if chosen:
                    radios = form_ctx.query_selector_all(f"input[type='radio'][name='{name}']")
                    clicked = False
                    for gr in radios:
                        rid = gr.get_attribute("id")
                        opt_lbl = ""
                        if rid:
                            lbl_el = form_ctx.query_selector(f"label[for='{rid}']")
                            if lbl_el:
                                opt_lbl = lbl_el.inner_text().strip()
                        if chosen.lower() in opt_lbl.lower() or opt_lbl.lower() in chosen.lower():
                            try:
                                gr.click(timeout=2000)
                                fields_filled += 1
                                add_log("FILL_LEVER", f"✅ Radio '{question[:30]}' → '{opt_lbl}'", "SUCCESS")
                                clicked = True
                            except Exception:
                                pass
                            break
                    if not clicked:
                        is_req = any(r.get_attribute("required") for r in radios if r)
                        pending_questions.append(
                            self._build_pending_question(field_id, question, "radio", is_req, opts)
                        )
                        add_log("FILL_LEVER", f"⚠️ Radio en attente : {question}", "WARNING")
                else:
                    is_req = False
                    try:
                        r0 = form_ctx.query_selector(f"input[type='radio'][name='{name}']")
                        if r0:
                            is_req = bool(r0.get_attribute("required") or r0.get_attribute("aria-required") == "true")
                    except Exception:
                        pass
                    important_radio_kws = ["sponsorship", "visa", "work authorization", "authoris", "contract"]
                    if is_req or any(kw in question.lower() for kw in important_radio_kws):
                        pending_questions.append(
                            self._build_pending_question(field_id, question, "radio", is_req, opts)
                        )
                        add_log("FILL_LEVER", f"⚠️ Radio important en attente : {question}", "WARNING")
        except Exception as e:
            add_log("FILL_LEVER", f"⚠️ Erreur scan radio groups : {str(e)[:80]}", "WARNING")

        add_log("FILL_LEVER", f"Remplissage terminé : {fields_filled} champ(s) rempli(s), {len(pending_questions)} question(s) en attente.", "SUCCESS")
        return {"success": fields_filled > 0, "pending_questions": pending_questions}

    def submit_form(self, page, add_log) -> bool:
        try:
            form_ctx = self._get_form_context(page, add_log)
            submit_btn = form_ctx.query_selector(
                "button#postulate, button[type='submit'], input[type='submit'], "
                "button.postings-btn, a.postings-btn"
            )
            if submit_btn:
                submit_btn.click()
                add_log("SUBMIT_LEVER", "Bouton de soumission cliqué.", "SUCCESS")
                time.sleep(5)
                return True
            else:
                add_log("SUBMIT_LEVER", "Bouton de soumission non trouvé.", "WARNING")
        except Exception as e:
            add_log("SUBMIT_LEVER", f"Échec de la soumission : {str(e)}", "WARNING")
        return False
