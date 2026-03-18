# dashboards/admin_dashboard.py
import streamlit as st
import matplotlib.pyplot as plt
from components.sidebar import sidebar
from components.charts import patient_line_chart, appointment_donut_chart
def admin_dashboard():
    # ---------- Session Defaults ----------
    st.session_state.setdefault("view", "dashboard")
    st.session_state.setdefault("selected_category", None)

    # ---------- Sidebar ----------
    category = sidebar([
        "Dashboard",
        "Appointments",
        "Patients",
        "Reports",
        "Doctors",
        "Features",
        "Forms, Tables & Charts",
        "Apps & Widgets",
        "Authentication",
        "Miscellaneous"
    ])

    # ---------- Admin Dashboard ----------
    st.markdown("## 🏥 Admin Dashboard")
    
    # Top metrics row
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # Patient Statistics Card
        st.markdown("### Patient Statistics")
        metric_cols = st.columns(2)
        with metric_cols[0]:
            st.metric("Total", "990", help="Total registered patients")
        with metric_cols[1]:
            # Gender breakdown
            st.markdown("**Gender Distribution**")
            st.markdown("🟣 Women 44%")
            st.markdown("⚪ Men 56%")
        
        sub_cols = st.columns(2)
        with sub_cols[0]:
            st.metric("New Patients", "67", delta="39%", delta_color="normal")
        with sub_cols[1]:
            st.metric("Old Patients", "27", delta="-64%", delta_color="inverse")
    
    with col2:
        # Your Patients Today
        st.markdown("### Your Patients Today")
        st.markdown("##### [All patients →](#)")
        
        # Patient list with doctor names
        patients_data = [
            ("10:30am", "Sarah Hostern", "Dr. Anderson", "Diagnostic: Records"),
            ("11:00am", "Dakota Smith", "Dr. Martinez", "Diagnostic: Stroke"),
            ("11:30am", "John Lane", "Dr. Johnson", "Diagnostic: Liver")
        ]
        
        for time, patient, doctor, diagnosis in patients_data:
            with st.container():
                p_col1, p_col2, p_col3 = st.columns([1, 3, 1])
                with p_col1:
                    st.markdown(f"**{time}**")
                with p_col2:
                    st.markdown(f"**{patient}**")
                    st.caption(f"👨‍⚕️ {doctor} • {diagnosis}")
                with p_col3:
                    st.button("⋮", key=f"menu_{patient}")
                st.divider()

    st.divider()
    
    # Second row - Recent queries and Lab test
    col3, col4 = st.columns([1, 1])
    
    with col3:
        st.markdown("### Recent queries")
        
        # Filter buttons
        filter_cols = st.columns([1, 1, 1, 3])
        with filter_cols[0]:
            st.button("All", type="primary", use_container_width=True)
        with filter_cols[1]:
            st.button("Unsaid", use_container_width=True)
        with filter_cols[2]:
            st.button("New", use_container_width=True)
        
        st.markdown("---")
        st.caption("14 Jun 2023 / 01:50PM")
        st.markdown("**Addiction blood bank bone marrow contagious disinfectants?**")
        query_cols = st.columns([2, 2, 1])
        with query_cols[0]:
            st.button("Read more", key="read1")
        with query_cols[1]:
            st.button("Reply", key="reply1")
        with query_cols[2]:
            st.markdown("💬")
    
    with col4:
        st.markdown("### Laboratory test")
        st.caption("🩺 Shawn Hampton")
        st.markdown("**Beta 2 Microglobulin Marker Test ®**")
        
        lab_cols = st.columns([2, 2, 2])
        with lab_cols[0]:
            st.button("Details", key="lab_details")
        with lab_cols[1]:
            st.button("Contact Patient", key="contact_pat")
        with lab_cols[2]:
            st.button("✓ Archive", type="primary", key="archive")

    st.divider()
    
    # Third row - Charts
    col5, col6, col7 = st.columns([2, 2, 2])
    
    with col5:
        st.markdown("### Analytics")
        patient_line_chart()
    
    with col6:
        st.markdown("### Appointments Overview")
        appointment_donut_chart()
    
    with col7:
        st.markdown("### Overall Appointments")
        # Simple bar chart for hourly appointments
        hours = ["8:00", "9:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00"]
        appointments = [12, 8, 15, 18, 6, 10, 16, 8, 15, 10, 17]
        
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.bar(hours, appointments, color='#5B47D8')
        ax.set_ylabel("Appointments")
        ax.tick_params(axis='x', rotation=45, labelsize=7)
        st.pyplot(fig)
    
    # Upcoming Appointments section
    st.divider()
    st.markdown("### Upcoming Appointments")
    st.caption("📅 Mon 22nd | Tue 23rd | Wed 24th | **Thursday July 25th 2024** | Fri 26th | Sat 27th")
    
    appointments_today = [
        ("Shawn Hampton", "Emergency appointment", "10:00", "$30"),
        ("Polly Paul", "USG + Consultation", "10:30", "$50"),
        ("Juken Doe", "Laboratory screening", "11:00", "$70")
    ]
    
    appt_cols = st.columns(3)
    for idx, (name, service, time, price) in enumerate(appointments_today):
        with appt_cols[idx]:
            st.markdown(f"**{name}**")
            st.caption(service)
            st.markdown(f"🕐 {time}  💵 {price}")
            st.button("📞", key=f"call_{idx}")