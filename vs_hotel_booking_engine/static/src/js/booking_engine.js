/** @odoo-module **/

function initBookingEngine() {
    const bookingWrapper = document.querySelector(".o_hotel_booking_engine");
    const reviewForm = document.getElementById("submit_review_form");

    // Review Form handler on Room Details page
    if (reviewForm) {
        reviewForm.addEventListener("submit", async function (e) {
            e.preventDefault();
            const btn = document.getElementById("btn_submit_review");
            const successMsg = document.getElementById("review_success_msg");
            const categoryId = reviewForm.getAttribute("data-category-id");
            const guestName = document.getElementById("rev_author_name").value;
            const guestEmail = document.getElementById("rev_author_email").value;
            const rating = document.getElementById("rev_rating_stars").value;
            const title = document.getElementById("rev_title").value;
            const comment = document.getElementById("rev_comment").value;

            btn.disabled = true;
            btn.innerHTML = '<i class="fa fa-spinner fa-spin me-1"></i> Submitting...';

            try {
                const response = await fetch("/hotel/review/submit", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        jsonrpc: "2.0",
                        method: "call",
                        params: {
                            category_id: parseInt(categoryId),
                            guest_name: guestName,
                            guest_email: guestEmail,
                            rating: parseInt(rating),
                            title: title,
                            comment: comment,
                        },
                    }),
                });
                const resData = await response.json();
                if (resData.result && resData.result.success) {
                    successMsg.classList.remove("d-none");
                    reviewForm.reset();
                    btn.innerHTML = 'Submitted';
                }
            } catch (err) {
                console.error("Error submitting review:", err);
                btn.disabled = false;
                btn.innerHTML = 'Submit Review';
            }
        });
    }

    // Homepage Hero Search Form handler (if on website homepage)
    const homeForm = document.getElementById("hotel_home_search_form");
    if (homeForm) {
        const homeCi = document.getElementById("home_booking_check_in");
        const homeCo = document.getElementById("home_booking_check_out");
        const homeGuests = document.getElementById("home_booking_guests_select");
        const homeAdults = document.getElementById("home_booking_adults");
        const homeChildren = document.getElementById("home_booking_children");

        if (homeCi && !homeCi.value) {
            const tomorrow = new Date();
            tomorrow.setDate(tomorrow.getDate() + 1);
            homeCi.value = tomorrow.toISOString().split("T")[0];
        }
        if (homeCo && !homeCo.value) {
            const dep = new Date();
            dep.setDate(dep.getDate() + 3);
            homeCo.value = dep.toISOString().split("T")[0];
        }

        if (homeGuests && homeAdults && homeChildren) {
            homeGuests.addEventListener("change", function () {
                const parts = this.value.split("_");
                homeAdults.value = parts[0] || "2";
                homeChildren.value = parts[1] || "0";
            });
        }
    }

    if (!bookingWrapper) {
        return;
    }

    // State Variables
    let currentStep = 1;
    let nights = 1;
    let currencySymbol = "$";
    let currencyId = null;
    let advancePercentage = 30.0;
    let advancePolicy = "optional";
    let availableCategories = [];
    let availableServices = [];
    let selectedRooms = []; // [{ room_id, room_number, category_id, category_name, price, image_url, nights }]
    let selectedServices = []; // [{ service_id, name, price }]
    let currentModalCategoryId = null;

    // DOM References
    const hotelSelect = document.getElementById("booking_hotel_id");
    const checkInInput = document.getElementById("booking_check_in");
    const checkOutInput = document.getElementById("booking_check_out");
    const guestsSelect = document.getElementById("booking_guests_select");
    const adultsInput = document.getElementById("booking_adults");
    const childrenInput = document.getElementById("booking_children");
    const currencySelect = document.getElementById("booking_currency_select");
    const searchBtn = document.getElementById("btn_search_availability");

    const step1Pane = document.getElementById("step1_room_showcase");
    const step2Pane = document.getElementById("step2_guest_and_services");
    const step3Pane = document.getElementById("step3_review_and_confirm");

    const categoriesContainer = document.getElementById("room_categories_container");
    const categoriesSpinner = document.getElementById("categories_loading_spinner");
    const selectedRoomsSummaryBar = document.getElementById("selected_rooms_summary_bar");
    const selectedRoomsCountBadge = document.getElementById("selected_rooms_count_badge");
    const selectedRoomsTotalDisplay = document.getElementById("selected_rooms_total_display");

    const addonServicesContainer = document.getElementById("addon_services_container");
    const orderSummaryRoomsList = document.getElementById("order_summary_rooms_list");
    const orderSummaryServicesList = document.getElementById("order_summary_services_list");
    const orderSummaryServicesItems = document.getElementById("order_summary_services_items");
    const summaryNightsCount = document.getElementById("summary_nights_count");
    const summaryRoomsSubtotal = document.getElementById("summary_rooms_subtotal");
    const summaryServicesSubtotal = document.getElementById("summary_services_subtotal");
    const summaryGrandTotal = document.getElementById("summary_grand_total");

    const btnGotoStep2 = document.getElementById("btn_goto_step2");
    const btnBacktoStep1 = document.getElementById("btn_backto_step1");
    const btnGotoStep3 = document.getElementById("btn_goto_step3");
    const btnBacktoStep2 = document.getElementById("btn_backto_step2");
    const btnSubmitFinalBooking = document.getElementById("btn_submit_final_booking");
    const submitSpinner = document.getElementById("submit_spinner");
    const bookingErrorAlert = document.getElementById("booking_error_alert");

    // Modal References & Bulletproof Show/Hide Controllers
    const roomModalEl = document.getElementById("room_selection_modal");

    function showModal(modalEl) {
        if (!modalEl) {
            console.error("[BookingEngine] Modal element not found!");
            return;
        }
        // 1. Try window.bootstrap
        if (typeof window.bootstrap !== "undefined" && window.bootstrap.Modal) {
            try {
                const inst = window.bootstrap.Modal.getOrCreateInstance ? window.bootstrap.Modal.getOrCreateInstance(modalEl) : new window.bootstrap.Modal(modalEl);
                inst.show();
                return;
            } catch (e) {
                console.warn("[BookingEngine] window.bootstrap.Modal show error:", e);
            }
        }
        // 2. Try window.Modal
        if (typeof window.Modal !== "undefined") {
            try {
                const inst = window.Modal.getOrCreateInstance ? window.Modal.getOrCreateInstance(modalEl) : new window.Modal(modalEl);
                inst.show();
                return;
            } catch (e) {
                console.warn("[BookingEngine] window.Modal show error:", e);
            }
        }
        // 3. Try jQuery plugin
        if (typeof window.$ !== "undefined" && typeof window.$.fn.modal === "function") {
            try {
                window.$(modalEl).modal("show");
                return;
            } catch (e) {
                console.warn("[BookingEngine] jQuery modal show error:", e);
            }
        }
        // 4. Native CSS/DOM Fallback
        modalEl.classList.add("show");
        modalEl.style.display = "block";
        modalEl.removeAttribute("aria-hidden");
        modalEl.setAttribute("aria-modal", "true");
        let backdrop = document.querySelector(".modal-backdrop");
        if (!backdrop) {
            backdrop = document.createElement("div");
            backdrop.className = "modal-backdrop fade show";
            document.body.appendChild(backdrop);
        }
        document.body.classList.add("modal-open");
    }

    function hideModal(modalEl) {
        if (!modalEl) return;
        // 1. Try window.bootstrap
        if (typeof window.bootstrap !== "undefined" && window.bootstrap.Modal) {
            try {
                const inst = window.bootstrap.Modal.getInstance ? window.bootstrap.Modal.getInstance(modalEl) : null;
                if (inst) { inst.hide(); return; }
            } catch (e) {}
        }
        // 2. Try window.Modal
        if (typeof window.Modal !== "undefined") {
            try {
                const inst = window.Modal.getInstance ? window.Modal.getInstance(modalEl) : null;
                if (inst) { inst.hide(); return; }
            } catch (e) {}
        }
        // 3. Try jQuery
        if (typeof window.$ !== "undefined" && typeof window.$.fn.modal === "function") {
            try {
                window.$(modalEl).modal("hide");
                return;
            } catch (e) {}
        }
        // 4. Native CSS/DOM Fallback
        modalEl.classList.remove("show");
        modalEl.style.display = "none";
        modalEl.setAttribute("aria-hidden", "true");
        modalEl.removeAttribute("aria-modal");
        document.querySelectorAll(".modal-backdrop").forEach(b => b.remove());
        document.body.classList.remove("modal-open");
    }

    // Attach native close handlers for dismiss buttons and backdrop
    if (roomModalEl) {
        roomModalEl.querySelectorAll('[data-bs-dismiss="modal"], .btn-close').forEach(btn => {
            btn.addEventListener("click", function (e) {
                e.preventDefault();
                hideModal(roomModalEl);
            });
        });
        roomModalEl.addEventListener("click", function (e) {
            if (e.target === roomModalEl) {
                hideModal(roomModalEl);
            }
        });
    }

    const modalCategoryTitle = document.getElementById("modal_category_title");
    const modalCategorySubtitle = document.getElementById("modal_category_subtitle");
    const modalCategoryPrice = document.getElementById("modal_category_price");
    const modalViewDetailsBtn = document.getElementById("modal_view_details_btn");
    const modalRoomsListContainer = document.getElementById("modal_rooms_list_container");
    const modalSelectionCounter = document.getElementById("modal_selection_counter");
    const btnModalConfirmRooms = document.getElementById("btn_modal_confirm_rooms");

    // Guest Inputs
    const guestNameInput = document.getElementById("guest_name");
    const guestEmailInput = document.getElementById("guest_email");
    const guestPhoneInput = document.getElementById("guest_phone");
    const guestCountryInput = document.getElementById("guest_country_id");
    const guestIdTypeInput = document.getElementById("guest_id_type");
    const guestIdNumberInput = document.getElementById("guest_id_number");
    const guestSpecialRequests = document.getElementById("guest_special_requests");
    const btnAddAccompanyingGuest = document.getElementById("btn_add_accompanying_guest");
    const accompanyingGuestsContainer = document.getElementById("accompanying_guests_container");
    const termsAgreeCheckbox = document.getElementById("terms_agree_checkbox");
    const advancePercentageLabel = document.getElementById("advance_percentage_label");
    const advanceDepositAmountDisplay = document.getElementById("advance_deposit_amount_display");

    // Stepper Navigation
    function goToStep(step) {
        currentStep = step;
        step1Pane.classList.toggle("d-none", currentStep !== 1);
        step2Pane.classList.toggle("d-none", currentStep !== 2);
        step3Pane.classList.toggle("d-none", currentStep !== 3);

        document.querySelectorAll(".o_step_item").forEach((item, idx) => {
            const stepNum = idx + 1;
            item.classList.toggle("active", stepNum === currentStep);
            item.classList.toggle("completed", stepNum < currentStep);
        });

        window.scrollTo({ top: 380, behavior: "smooth" });
    }

    // Guest Selector Sync
    if (guestsSelect) {
        guestsSelect.addEventListener("change", function () {
            const val = this.value.split("_");
            adultsInput.value = val[0];
            childrenInput.value = val[1];
        });
    }

    // Error Alert Helper
    function showError(msg) {
        if (!bookingErrorAlert) return;
        bookingErrorAlert.textContent = msg;
        bookingErrorAlert.classList.remove("d-none");
        window.scrollTo({ top: bookingErrorAlert.offsetTop - 80, behavior: "smooth" });
    }

    function clearError() {
        if (!bookingErrorAlert) return;
        bookingErrorAlert.textContent = "";
        bookingErrorAlert.classList.add("d-none");
    }

    // Multi-Currency and Hotel Selection Sync
    if (currencySelect) {
        currencySelect.addEventListener("change", function () {
            currencyId = this.value;
            if (availableCategories.length > 0) {
                fetchAvailability();
            }
        });
    }

    if (hotelSelect) {
        hotelSelect.addEventListener("change", function () {
            selectedRooms = [];
            selectedServices = [];
            if (availableCategories.length > 0) {
                fetchAvailability();
            }
        });
    }

    if (searchBtn) {
        searchBtn.addEventListener("click", function (e) {
            e.preventDefault();
            console.log("[BookingEngine] Search Stays button clicked");
            fetchAvailability();
            const showcase = document.getElementById("step1_room_showcase");
            if (showcase) {
                showcase.scrollIntoView({ behavior: "smooth", block: "start" });
            }
        });
    }

    // Availability Fetch
    async function fetchAvailability() {
        clearError();
        const hotelId = hotelSelect ? hotelSelect.value : null;
        const checkIn = checkInInput.value;
        const checkOut = checkOutInput.value;

        if (!hotelId) {
            showError("Please select a destination / hotel.");
            return;
        }
        if (!checkIn || !checkOut) {
            showError("Please select both check-in and departure dates.");
            return;
        }
        if (checkIn >= checkOut) {
            showError("Departure date must be after check-in date.");
            return;
        }

        if (categoriesSpinner) categoriesSpinner.classList.remove("d-none");
        if (categoriesContainer) categoriesContainer.innerHTML = "";

        try {
            const response = await fetch("/hotel/booking/api/availability", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    method: "call",
                    params: {
                        hotel_id: parseInt(hotelId),
                        check_in: checkIn,
                        check_out: checkOut,
                        adults: parseInt(adultsInput.value || 2),
                        children: parseInt(childrenInput.value || 0),
                        currency_id: currencyId ? parseInt(currencyId) : null,
                    },
                }),
            });

            const resData = await response.json();
            const data = resData.result;

            if (categoriesSpinner) categoriesSpinner.classList.add("d-none");

            if (data.error) {
                showError(data.error);
                return;
            }

            nights = data.nights || 1;
            currencySymbol = data.currency ? data.currency.symbol : "$";
            currencyId = data.currency ? data.currency.id : null;
            advancePercentage = data.advance_percentage || 30.0;
            advancePolicy = data.policy || "optional";
            availableCategories = data.categories || [];
            availableServices = data.services || [];

            // Update Theme Colors dynamically if hotel returns them
            if (data.hotel && bookingWrapper) {
                bookingWrapper.style.setProperty("--hotel-primary", data.hotel.primary_color || "#1e3a8a");
                bookingWrapper.style.setProperty("--hotel-secondary", data.hotel.secondary_color || "#2563eb");
                bookingWrapper.style.setProperty("--hotel-accent", data.hotel.accent_color || "#f59e0b");
            }

            renderRoomCategories();
            renderAddonServices();
            updateSelectedRoomsUI();
        } catch (err) {
            if (categoriesSpinner) categoriesSpinner.classList.add("d-none");
            showError("Unable to connect to availability service. Please try again.");
            console.error(err);
        }
    }

    // Render Room Categories Grid
    function renderRoomCategories() {
        if (!categoriesContainer) return;
        categoriesContainer.innerHTML = "";

        if (availableCategories.length === 0) {
            categoriesContainer.innerHTML = `
                <div class="col-12 text-center py-5">
                    <div class="card border-0 shadow-sm rounded-4 p-4 p-md-5 mx-auto bg-white" style="max-width: 600px;">
                        <div class="rounded-circle bg-light d-inline-flex align-items-center justify-content-center mb-3 mx-auto" style="width: 72px; height: 72px;">
                            <i class="fa fa-bed fa-2x text-muted"></i>
                        </div>
                        <h5 class="fw-bold text-dark mb-2">No Rooms Available for Selected Criteria</h5>
                        <p class="text-muted small mb-0">No accommodations were found matching your travel dates and guest occupancy (${adultsInput ? adultsInput.value : 2} Adults, ${childrenInput ? childrenInput.value : 0} Children). Please adjust your dates or guest count and click Search Stays again.</p>
                    </div>
                </div>
            `;
            return;
        }

        availableCategories.forEach(cat => {
            const availCount = cat.available_rooms.length;
            const starsHtml = '<i class="fa fa-star text-warning"></i>'.repeat(Math.round(cat.rating_avg || 5));
            const selectedForThisCat = selectedRooms.filter(r => r.category_id === cat.id).length;
            const maxGuests = cat.max_occupancy || (cat.max_adults + cat.max_children);

            let amenitiesHtml = "";
            (cat.amenities || []).slice(0, 3).forEach(am => {
                amenitiesHtml += `<span class="o_amenity_pill small"><i class="fa fa-check text-success me-1"></i>${am.name}</span>`;
            });

            const col = document.createElement("div");
            col.className = "col-12 col-md-6 col-lg-4";
            col.innerHTML = `
                <div class="o_room_category_card h-100 d-flex flex-column shadow-sm rounded-4 overflow-hidden border bg-white position-relative">
                    <!-- Top Image Area -->
                    <div class="position-relative overflow-hidden" style="height: 220px; background-color: #f1f5f9;">
                        <img src="${cat.image_url}" class="o_room_card_img" alt="${cat.name}"/>
                        
                        <!-- Top Left: Availability Badge -->
                        <div class="position-absolute top-0 start-0 m-3">
                            <span class="badge bg-white bg-opacity-95 text-dark shadow-sm px-2.5 py-1.5 rounded-pill fw-semibold small">
                                <i class="fa fa-circle text-success me-1" style="font-size: 0.55rem;"></i>${availCount} Available
                            </span>
                        </div>

                        <!-- Top Right: Max Guests Badge -->
                        <div class="position-absolute top-0 end-0 m-3">
                            <span class="badge bg-dark bg-opacity-75 text-white shadow-sm px-2.5 py-1.5 rounded-pill small fw-normal">
                                <i class="fa fa-users me-1 text-white-50"></i>Up to ${maxGuests} Guests
                            </span>
                        </div>

                        <!-- Bottom Image Info Bar -->
                        <div class="position-absolute bottom-0 start-0 end-0 p-2.5 bg-gradient-dark-bottom d-flex justify-content-between align-items-center text-white small">
                            <span><i class="fa fa-bed me-1 text-hotel-accent"></i>${cat.bed_type || 'King Bed'}</span>
                            <span><i class="fa fa-expand me-1 text-hotel-accent"></i>${cat.room_size || '35'} sq.m</span>
                        </div>
                    </div>

                    <!-- Card Body -->
                    <div class="p-3.5 p-lg-4 d-flex flex-column flex-grow-1">
                        <div class="d-flex justify-content-between align-items-start mb-1">
                            <h5 class="fw-bold text-dark mb-0">${cat.name}</h5>
                            <div class="o_rating_stars small" title="Rated ${cat.rating_avg} / 5">
                                ${starsHtml}
                                <span class="text-muted fw-bold ms-1">(${cat.review_count || 0})</span>
                            </div>
                        </div>

                        <p class="small text-muted mb-3 flex-grow-1" style="line-height: 1.5;">
                            ${cat.description ? (cat.description.length > 90 ? cat.description.slice(0, 90) + '...' : cat.description) : 'Premium comfort with tailored hospitality and modern amenities.'}
                        </p>

                        <!-- Amenities -->
                        <div class="d-flex flex-wrap gap-1 mb-3">
                            ${amenitiesHtml}
                        </div>

                        <!-- Footer: Minimized Price & Select Rooms Button -->
                        <div class="d-flex align-items-center justify-content-between pt-3 border-top mt-auto">
                            <div>
                                <span class="text-muted text-uppercase fw-semibold d-block" style="font-size: 0.65rem; letter-spacing: 0.5px;">Starting from</span>
                                <div class="d-flex align-items-baseline gap-1">
                                    <span class="fw-bold text-hotel-primary" style="font-size: 1.15rem;">${currencySymbol}${cat.nightly_price.toFixed(2)}</span>
                                    <span class="text-muted" style="font-size: 0.78rem;">/night</span>
                                </div>
                            </div>
                            <button type="button" class="btn btn-hotel-primary rounded-pill px-3 py-1.5 fw-semibold shadow-sm btn_open_room_modal"
                                    data-category-id="${cat.id}">
                                ${selectedForThisCat > 0 ? `<i class="fa fa-check-circle me-1"></i> ${selectedForThisCat} Selected` : '<i class="fa fa-plus-circle me-1"></i> Select Rooms'}
                            </button>
                        </div>
                    </div>
                </div>
            `;
            categoriesContainer.appendChild(col);
        });

        // Attach event listeners to "Select Rooms" buttons
        document.querySelectorAll(".btn_open_room_modal").forEach(btn => {
            btn.addEventListener("click", function () {
                const catId = parseInt(this.getAttribute("data-category-id"));
                openRoomModal(catId);
            });
        });
    }

    // Open Room Selection Modal Popup
    function openRoomModal(catId) {
        currentModalCategoryId = catId;
        const cat = availableCategories.find(c => c.id === catId);
        if (!cat) return;

        modalCategoryTitle.textContent = `${cat.name} — Room Selection`;
        modalCategorySubtitle.textContent = `Select one or multiple rooms (${cat.bed_type}, ${cat.room_size || '35'} sq.m) · Up to ${cat.max_occupancy || (cat.max_adults + cat.max_children)} guests per room`;
        modalCategoryPrice.innerHTML = `<span style="font-size: 1.1rem; font-weight: 700;">${currencySymbol}${cat.nightly_price.toFixed(2)}</span> <span class="text-muted" style="font-size: 0.8rem;">/night</span>`;
        modalViewDetailsBtn.href = `/hotel/room_type/${cat.id}`;

        modalRoomsListContainer.innerHTML = "";

        cat.available_rooms.forEach(room => {
            const isChecked = selectedRooms.some(sr => sr.room_id === room.id);
            const roomCard = document.createElement("div");
            roomCard.className = "col-12 col-md-6";
            roomCard.innerHTML = `
                <div class="o_modal_room_card d-flex align-items-center justify-content-between ${isChecked ? 'selected' : ''}">
                    <div class="form-check d-flex align-items-center gap-2 mb-0">
                        <input class="form-check-input modal_room_checkbox" type="checkbox"
                               value="${room.id}" id="chk_room_${room.id}" ${isChecked ? 'checked' : ''}
                               data-room-id="${room.id}"
                               data-room-number="${room.room_number}"
                               data-category-id="${cat.id}"
                               data-category-name="${cat.name}"
                               data-price="${cat.nightly_price}"
                               data-image="${room.image_url || cat.image_url}"/>
                        <label class="form-check-label fw-bold text-dark cursor-pointer mb-0" for="chk_room_${room.id}">
                            Room ${room.room_number}
                        </label>
                    </div>
                    <div class="text-end">
                        <span class="badge bg-light text-dark border small">${room.floor || 'Floor 1'}</span>
                        <a href="/hotel/room/${room.id}" target="_blank" class="small text-decoration-none d-block mt-1 text-hotel-primary" title="View room specifications & photos in new tab">
                            <i class="fa fa-external-link"></i> Details
                        </a>
                    </div>
                </div>
            `;
            modalRoomsListContainer.appendChild(roomCard);
        });

        updateModalSelectionCounter();

        // Checkbox toggle highlight
        document.querySelectorAll(".modal_room_checkbox").forEach(chk => {
            chk.addEventListener("change", function () {
                const parent = this.closest(".o_modal_room_card");
                if (parent) parent.classList.toggle("selected", this.checked);
                updateModalSelectionCounter();
            });
        });

        showModal(roomModalEl);
    }

    function updateModalSelectionCounter() {
        const checkedCount = document.querySelectorAll(".modal_room_checkbox:checked").length;
        if (modalSelectionCounter) {
            modalSelectionCounter.textContent = `${checkedCount} room(s) checked in this category`;
        }
    }

    // Modal Done / Add Selected Rooms
    if (btnModalConfirmRooms) {
        btnModalConfirmRooms.addEventListener("click", function () {
            if (!currentModalCategoryId) return;

            // Remove existing selected rooms of this category
            selectedRooms = selectedRooms.filter(r => r.category_id !== currentModalCategoryId);

            // Add newly checked rooms
            document.querySelectorAll(".modal_room_checkbox:checked").forEach(chk => {
                selectedRooms.push({
                    room_id: parseInt(chk.getAttribute("data-room-id")),
                    room_number: chk.getAttribute("data-room-number"),
                    category_id: parseInt(chk.getAttribute("data-category-id")),
                    category_name: chk.getAttribute("data-category-name"),
                    price: parseFloat(chk.getAttribute("data-price")),
                    image_url: chk.getAttribute("data-image"),
                    nights: nights,
                });
            });

            hideModal(roomModalEl);

            renderRoomCategories();
            updateSelectedRoomsUI();
        });
    }

    // Update Selected Rooms Sticky Bar & Cart
    function updateSelectedRoomsUI() {
        const count = selectedRooms.length;

        if (count > 0) {
            if (selectedRoomsSummaryBar) selectedRoomsSummaryBar.classList.remove("d-none");
            if (selectedRoomsCountBadge) selectedRoomsCountBadge.textContent = `${count} Room(s) Selected`;
        } else {
            if (selectedRoomsSummaryBar) selectedRoomsSummaryBar.classList.add("d-none");
        }

        // Calculations
        const roomsTotal = selectedRooms.reduce((sum, r) => sum + (r.price * nights), 0);
        const servicesTotal = selectedServices.reduce((sum, s) => sum + s.price, 0);
        const grandTotal = roomsTotal + servicesTotal;
        const advanceRequired = roundToTwo(grandTotal * (advancePercentage / 100.0));

        if (selectedRoomsTotalDisplay) selectedRoomsTotalDisplay.textContent = `${currencySymbol}${roomsTotal.toFixed(2)}`;
        if (summaryRoomsSubtotal) summaryRoomsSubtotal.textContent = `${currencySymbol}${roomsTotal.toFixed(2)}`;
        if (summaryServicesSubtotal) summaryServicesSubtotal.textContent = `${currencySymbol}${servicesTotal.toFixed(2)}`;
        if (summaryGrandTotal) summaryGrandTotal.textContent = `${currencySymbol}${grandTotal.toFixed(2)}`;
        if (summaryNightsCount) summaryNightsCount.textContent = `${nights} Night(s)`;
        if (advancePercentageLabel) advancePercentageLabel.textContent = `${advancePercentage}%`;
        if (advanceDepositAmountDisplay) advanceDepositAmountDisplay.textContent = `${currencySymbol}${advanceRequired.toFixed(2)}`;

        // Populate Sticky Stay Summary in Step 2
        if (orderSummaryRoomsList) {
            orderSummaryRoomsList.innerHTML = "";
            selectedRooms.forEach(r => {
                const item = document.createElement("div");
                item.className = "d-flex align-items-center gap-2 mb-2 pb-2 border-bottom";
                item.innerHTML = `
                    <img src="${r.image_url}" class="rounded-2 shadow-sm" style="width: 48px; height: 48px; object-fit: cover;"/>
                    <div class="flex-grow-1">
                        <strong class="text-dark d-block small">Room ${r.room_number}</strong>
                        <small class="text-muted">${r.category_name}</small>
                    </div>
                    <div class="text-end">
                        <strong class="text-hotel-primary small">${currencySymbol}${(r.price * nights).toFixed(2)}</strong>
                    </div>
                `;
                orderSummaryRoomsList.appendChild(item);
            });
        }
    }

    // Render Add-on Services Checklist
    function renderAddonServices() {
        if (!addonServicesContainer) return;
        addonServicesContainer.innerHTML = "";

        if (availableServices.length === 0) {
            const card = document.getElementById("addon_services_card");
            if (card) card.classList.add("d-none");
            return;
        }

        availableServices.forEach(s => {
            const isChecked = selectedServices.some(ss => ss.service_id === s.id);
            const col = document.createElement("div");
            col.className = "col-12 col-md-6";
            col.innerHTML = `
                <div class="o_service_card d-flex align-items-center gap-3 ${isChecked ? 'selected' : ''}">
                    <input class="form-check-input service_checkbox" type="checkbox" value="${s.id}" id="chk_service_${s.id}"
                           data-service-id="${s.id}" data-name="${s.name}" data-price="${s.price}" ${isChecked ? 'checked' : ''}/>
                    <div class="flex-grow-1">
                        <label class="form-check-label fw-bold text-dark d-block cursor-pointer mb-0" for="chk_service_${s.id}">
                            ${s.name}
                        </label>
                        <small class="text-muted d-block">${s.description || 'Premium hotel add-on service'}</small>
                    </div>
                    <div class="text-end">
                        <strong class="text-hotel-primary">${s.is_complimentary ? 'Free' : currencySymbol + s.price.toFixed(2)}</strong>
                    </div>
                </div>
            `;
            addonServicesContainer.appendChild(col);
        });

        // Addon services selection listeners
        document.querySelectorAll(".service_checkbox").forEach(chk => {
            chk.addEventListener("change", function () {
                const sId = parseInt(this.getAttribute("data-service-id"));
                const name = this.getAttribute("data-name");
                const price = parseFloat(this.getAttribute("data-price"));
                const card = this.closest(".o_service_card");
                if (card) card.classList.toggle("selected", this.checked);

                if (this.checked) {
                    if (!selectedServices.some(ss => ss.service_id === sId)) {
                        selectedServices.push({ service_id: sId, name: name, price: price });
                    }
                } else {
                    selectedServices = selectedServices.filter(ss => ss.service_id !== sId);
                }

                // Update services in summary
                if (orderSummaryServicesList) {
                    orderSummaryServicesList.classList.toggle("d-none", selectedServices.length === 0);
                    if (orderSummaryServicesItems) {
                        orderSummaryServicesItems.innerHTML = "";
                        selectedServices.forEach(ss => {
                            orderSummaryServicesItems.innerHTML += `
                                <div class="d-flex justify-content-between small text-muted mb-1">
                                    <span>${ss.name}</span>
                                    <strong class="text-dark">${currencySymbol}${ss.price.toFixed(2)}</strong>
                                </div>
                            `;
                        });
                    }
                }

                updateSelectedRoomsUI();
            });
        });
    }

    // Accompanying Guests Dynamic Rows
    if (btnAddAccompanyingGuest && accompanyingGuestsContainer) {
        btnAddAccompanyingGuest.addEventListener("click", function () {
            const rowId = Date.now();
            const row = document.createElement("div");
            row.className = "row g-2 align-items-center mb-2 accompanying_guest_row p-2 border rounded-3 bg-light";
            row.id = `guest_row_${rowId}`;
            row.innerHTML = `
                <div class="col-12 col-md-4">
                    <input type="text" class="form-control form-control-sm accompanying_name" placeholder="Companion Full Name" required/>
                </div>
                <div class="col-6 col-md-3">
                    <select class="form-select form-select-sm accompanying_id_type">
                        <option value="national_id">National ID / CNIC</option>
                        <option value="passport">Passport</option>
                        <option value="driving_license">Driving License</option>
                    </select>
                </div>
                <div class="col-6 col-md-3">
                    <input type="text" class="form-control form-control-sm accompanying_id_number" placeholder="ID Number"/>
                </div>
                <div class="col-12 col-md-2 text-end">
                    <button type="button" class="btn btn-sm btn-outline-danger btn_remove_guest" data-row-id="guest_row_${rowId}">
                        <i class="fa fa-trash"></i>
                    </button>
                </div>
            `;
            accompanyingGuestsContainer.appendChild(row);

            row.querySelector(".btn_remove_guest").addEventListener("click", function () {
                document.getElementById(this.getAttribute("data-row-id")).remove();
            });
        });
    }

    // Navigation Buttons
    if (btnGotoStep2) {
        btnGotoStep2.addEventListener("click", function () {
            if (selectedRooms.length === 0) {
                showError("Please select at least one room to proceed.");
                return;
            }
            clearError();
            goToStep(2);
        });
    }

    if (btnBacktoStep1) {
        btnBacktoStep1.addEventListener("click", function () {
            goToStep(1);
        });
    }

    if (btnGotoStep3) {
        btnGotoStep3.addEventListener("click", function () {
            clearError();
            if (!guestNameInput.value.trim()) {
                showError("Please enter the primary guest's legal full name.");
                guestNameInput.focus();
                return;
            }
            if (!guestEmailInput.value.trim() || !guestEmailInput.value.includes("@")) {
                showError("Please provide a valid email address.");
                guestEmailInput.focus();
                return;
            }
            if (!guestPhoneInput.value.trim()) {
                showError("Please provide a valid contact phone or WhatsApp number.");
                guestPhoneInput.focus();
                return;
            }
            if (!guestIdNumberInput.value.trim()) {
                showError("Please provide the legal Identification Document (CNIC / Passport) number.");
                guestIdNumberInput.focus();
                return;
            }

            goToStep(3);
        });
    }

    if (btnBacktoStep2) {
        btnBacktoStep2.addEventListener("click", function () {
            goToStep(2);
        });
    }

    // Final Booking Submission
    if (btnSubmitFinalBooking) {
        btnSubmitFinalBooking.addEventListener("click", async function (e) {
            e.preventDefault();
            clearError();

            if (!termsAgreeCheckbox.checked) {
                showError("You must agree to the reservation conditions and cancellation terms to confirm your booking.");
                return;
            }

            // Collect accompanying guests
            const accompanyingList = [];
            document.querySelectorAll(".accompanying_guest_row").forEach(row => {
                const name = row.querySelector(".accompanying_name").value.trim();
                const idType = row.querySelector(".accompanying_id_type").value;
                const idNum = row.querySelector(".accompanying_id_number").value.trim();
                if (name) {
                    accompanyingList.push({
                        name: name,
                        id_type: idType,
                        id_number: idNum,
                        age_category: "adult",
                    });
                }
            });

            // Payment choice
            const paymentChoice = document.querySelector("input[name='payment_choice_radio']:checked").value;

            btnSubmitFinalBooking.disabled = true;
            if (submitSpinner) submitSpinner.classList.remove("d-none");

            const payload = {
                hotel_id: parseInt(hotelSelect.value),
                check_in: checkInInput.value,
                check_out: checkOutInput.value,
                adults: parseInt(adultsInput.value || 2),
                children: parseInt(childrenInput.value || 0),
                guest_name: guestNameInput.value.trim(),
                guest_email: guestEmailInput.value.trim(),
                guest_phone: guestPhoneInput.value.trim(),
                guest_country_id: guestCountryInput ? parseInt(guestCountryInput.value) : false,
                guest_id_type: guestIdTypeInput.value,
                guest_id_number: guestIdNumberInput.value.trim(),
                special_requests: guestSpecialRequests ? guestSpecialRequests.value.trim() : "",
                rooms: selectedRooms.map(r => ({
                    room_id: r.room_id,
                    room_type_id: r.category_id,
                    nightly_price: r.price,
                })),
                services: selectedServices.map(s => s.service_id),
                accompanying_guests: accompanyingList,
                payment_choice: paymentChoice,
            };

            try {
                const response = await fetch("/hotel/booking/submit", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        jsonrpc: "2.0",
                        method: "call",
                        params: payload,
                    }),
                });

                const resData = await response.json();
                const data = resData.result;

                if (data.error) {
                    showError(data.error);
                    btnSubmitFinalBooking.disabled = false;
                    if (submitSpinner) submitSpinner.classList.add("d-none");
                    return;
                }

                if (data.success && data.redirect_url) {
                    window.location.href = data.redirect_url;
                }
            } catch (err) {
                btnSubmitFinalBooking.disabled = false;
                if (submitSpinner) submitSpinner.classList.add("d-none");
                showError("An error occurred while confirming your booking. Please try again.");
                console.error(err);
            }
        });
    }

    function roundToTwo(num) {
        return Math.round((num + Number.EPSILON) * 100) / 100;
    }

    function renderInitialPrompt() {
        if (!categoriesContainer) return;
        categoriesContainer.innerHTML = `
            <div class="col-12 text-center py-5">
                <div class="card border-0 shadow-sm rounded-4 p-4 p-md-5 mx-auto bg-white" style="max-width: 650px;">
                    <div class="rounded-circle bg-light d-inline-flex align-items-center justify-content-center mb-3 mx-auto" style="width: 72px; height: 72px;">
                        <i class="fa fa-calendar-check-o fa-2x text-hotel-primary"></i>
                    </div>
                    <h4 class="fw-bold text-dark mb-2">Find Your Ideal Room</h4>
                    <p class="text-muted mb-4 small" style="max-width: 480px; margin: 0 auto; line-height: 1.6;">
                        Please select your destination hotel, check-in and departure dates, and number of guests in the search bar above, then click <strong>Search Stays</strong> to discover available luxury rooms and rates.
                    </p>
                    <div>
                        <button type="button" class="btn btn-hotel-primary rounded-pill px-4 py-2 fw-semibold shadow-sm" id="btn_prompt_search_stays">
                            <i class="fa fa-search me-1"></i> Search Stays Now
                        </button>
                    </div>
                </div>
            </div>
        `;
        const promptBtn = document.getElementById("btn_prompt_search_stays");
        if (promptBtn && searchBtn) {
            promptBtn.addEventListener("click", () => searchBtn.click());
        }
    }

    // Only query room types when search parameters are present in URL or Search button is clicked
    const urlParams = new URLSearchParams(window.location.search);
    const hasSearchQuery = urlParams.has("check_in") || urlParams.has("check_out");

    if (hasSearchQuery && checkInInput && checkOutInput && hotelSelect && hotelSelect.value) {
        console.log("[BookingEngine] Initializing availability fetch from URL parameters for hotel", hotelSelect.value);
        fetchAvailability();
        setTimeout(() => {
            const showcase = document.getElementById("step1_room_showcase");
            if (showcase) {
                showcase.scrollIntoView({ behavior: "smooth", block: "start" });
            }
        }, 500);
    } else {
        renderInitialPrompt();
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initBookingEngine);
} else {
    initBookingEngine();
}
