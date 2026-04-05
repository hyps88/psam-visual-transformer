# ... [Initialization and Helpers remain LOCKED] ...

# --- TAB 1: TRANSFORMER ---
with tab_run:
    uploaded_files = st.file_uploader("Drag & Drop", type=['jpg', 'png', 'webp'], accept_multiple_files=True, label_visibility="collapsed")

    if uploaded_files:
        # Gallery Logic
        if st.session_state.img_idx >= len(uploaded_files): st.session_state.img_idx = 0
        cur_file = uploaded_files[st.session_state.img_idx]
        
        st.write(" ")
        cust_active = st.toggle("Custom Settings", value=False)
        selected_formats = []

        if cust_active:
            # ... [Custom Settings Logic remains LOCKED] ...
            selected_formats.append({"label": "Custom", "width": cust_w, "height": cust_h, "ext": cust_ext, "quality": cust_q})

        st.write(" ")
        if st.toggle("Templates", key="show_templates"):
            # ... [Templates Logic remains LOCKED] ...
            pass

        st.divider()
        # Toggle removed. Function is now a backend process
        if st.button("GENERATE ALL ASSETS", use_container_width=True):
            if selected_formats:
                zip_buffer = io.BytesIO()
                # ... [Generation Loop remains LOCKED] ...
                
                # --- AUTOMATED BACKEND SLACK NOTIFICATION ---
                try:
                    import slack_notifier
                    slack_notifier.send_notification(
                        user_name="GG", #
                        project_name=st.session_state.proj_name,
                        file_count=len(uploaded_files),
                        formats=selected_formats
                    )
                except Exception:
                    pass # Ensure main app functionality never breaks
                
                st.success("Batch Generated."); st.download_button("DOWNLOAD ZIP", data=zip_buffer.getvalue(), file_name=f"{sanitize(st.session_state.proj_name)}.zip", mime="application/zip")

# ... [Tabs 2 & 3 remain LOCKED] ...
