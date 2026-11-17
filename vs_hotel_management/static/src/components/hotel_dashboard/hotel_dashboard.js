/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUnmount, proxy, signal } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class HotelDashboard extends Component {
    static template = "vs_hotel_management.HotelDashboard";

    trendChartRef = signal.ref();
    sourceChartRef = signal.ref();

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.charts = {};

        this.state = proxy({
            isLoading: true,
            selectedHotelId: "all",
            selectedPreset: "today",
            customDateFrom: "",
            customDateTo: "",
            hotels: [],
            currencySymbol: "$",
            kpis: {},
            queues: {},
            housekeeping: {},
            chartsData: {},
            upcomingArrivals: [],
            upcomingDepartures: [],
            availableRooms: [],
        });

        onWillStart(async () => {
            await this.loadData();
        });

        onMounted(() => {
            this.renderAllCharts();
        });

        onWillUnmount(() => {
            this.destroyAllCharts();
        });
    }

    async loadData() {
        try {
            this.state.isLoading = true;
            const data = await this.orm.call(
                "hotel.dashboard",
                "get_dashboard_data",
                [],
                {
                    hotel_id: this.state.selectedHotelId,
                    preset: this.state.selectedPreset,
                    date_from: this.state.customDateFrom || null,
                    date_to: this.state.customDateTo || null,
                }
            );

            this.state.hotels = data.hotels || [];
            this.state.currencySymbol = data.currency_symbol || "$";
            this.state.kpis = data.kpis || {};
            this.state.queues = data.queues || {};
            this.state.housekeeping = data.housekeeping || {};
            this.state.chartsData = data.charts || {};
            this.state.upcomingArrivals = data.upcoming_arrivals || [];
            this.state.upcomingDepartures = data.upcoming_departures || [];
            this.state.availableRooms = data.available_rooms_list || [];
        } catch (error) {
            console.error("Error loading hotel dashboard data:", error);
            this.notification.add(_t("Failed to load hotel dashboard metrics."), {
                type: "danger",
            });
        } finally {
            this.state.isLoading = false;
        }
    }

    async reload() {
        await this.loadData();
        this.renderAllCharts();
    }

    async onHotelChange(ev) {
        this.state.selectedHotelId = ev.target.value;
        await this.reload();
    }

    async onPresetChange(preset) {
        this.state.selectedPreset = preset;
        await this.reload();
    }

    onCustomDateFromChange(ev) {
        this.state.customDateFrom = ev.target.value;
    }

    onCustomDateToChange(ev) {
        this.state.customDateTo = ev.target.value;
    }

    async applyDateSearch() {
        if (!this.state.customDateFrom || !this.state.customDateTo) {
            this.notification.add(_t("Please select both From and To dates to filter."), {
                type: "warning",
            });
            return;
        }
        this.state.selectedPreset = "custom";
        await this.reload();
    }

    // =========================================================================
    // QUICK RESERVATION FOR AVAILABLE ROOMS
    // =========================================================================

    async quickBookRoom(room) {
        try {
            this.state.isLoading = true;
            const action = await this.orm.call(
                "hotel.dashboard",
                "action_quick_book_room",
                [room.id]
            );
            if (action) {
                this.action.doAction(action);
            }
        } catch (error) {
            console.warn("Could not quick-create via RPC, opening form with defaults:", error);
            this.action.doAction({
                name: _t("New Reservation - Room %s", room.room_number),
                type: "ir.actions.act_window",
                res_model: "hotel.reservation",
                views: [[false, "form"]],
                target: "current",
                context: {
                    default_hotel_id: room.hotel_id,
                    default_line_ids: [
                        [0, 0, {
                            room_id: room.id,
                            room_category_id: room.category_id,
                        }]
                    ],
                },
            });
        } finally {
            this.state.isLoading = false;
        }
    }

    // =========================================================================
    // SMART & INFORMATIVE CHARTS
    // =========================================================================

    renderAllCharts() {
        if (typeof Chart === "undefined") {
            return;
        }
        this.renderTrendChart();
        this.renderSourceChart();
    }

    destroyAllCharts() {
        for (const key of Object.keys(this.charts)) {
            if (this.charts[key]) {
                this.charts[key].destroy();
                this.charts[key] = null;
            }
        }
    }

    renderTrendChart() {
        const canvas = this.trendChartRef.el;
        if (!canvas) return;
        if (this.charts.trend) this.charts.trend.destroy();

        const data = this.state.chartsData.trend || { labels: [], occupied: [], revenue: [] };
        const ctx = canvas.getContext("2d");

        const currencySym = this.state.currencySymbol;

        this.charts.trend = new Chart(ctx, {
            type: "bar",
            data: {
                labels: data.labels,
                datasets: [
                    {
                        label: _t("Occupied Rooms"),
                        data: data.occupied,
                        backgroundColor: "#334155",
                        hoverBackgroundColor: "#0f172a",
                        borderRadius: 6,
                        barThickness: 24,
                        yAxisID: "yRooms",
                    },
                    {
                        label: _t("Room Revenue"),
                        data: data.revenue,
                        type: "line",
                        borderColor: "#10b981",
                        backgroundColor: "rgba(16, 185, 129, 0.08)",
                        borderWidth: 2.5,
                        pointBackgroundColor: "#ffffff",
                        pointBorderColor: "#10b981",
                        pointBorderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        fill: true,
                        tension: 0.35,
                        yAxisID: "yRev",
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: {
                        position: "top",
                        labels: {
                            boxWidth: 10,
                            font: { size: 12, weight: "600" },
                            padding: 14,
                        },
                    },
                    tooltip: {
                        backgroundColor: "#0f172a",
                        titleFont: { size: 13, weight: "bold" },
                        bodyFont: { size: 12 },
                        padding: 10,
                        cornerRadius: 8,
                        callbacks: {
                            label: function (context) {
                                if (context.dataset.yAxisID === "yRev") {
                                    return ` Revenue: ${currencySym}${Number(context.raw).toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
                                }
                                return ` Occupied: ${context.raw} rooms`;
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { font: { size: 11, weight: "500" }, color: "#64748b" },
                    },
                    yRooms: {
                        type: "linear",
                        display: true,
                        position: "left",
                        title: { display: true, text: _t("Rooms Occupied"), color: "#64748b", font: { size: 11 } },
                        grid: { color: "#f1f5f9" },
                        ticks: { stepSize: 1, color: "#64748b" },
                    },
                    yRev: {
                        type: "linear",
                        display: true,
                        position: "right",
                        title: { display: true, text: _t("Revenue"), color: "#64748b", font: { size: 11 } },
                        grid: { drawOnChartArea: false },
                        ticks: {
                            color: "#64748b",
                            callback: function (val) {
                                return `${currencySym}${val}`;
                            },
                        },
                    },
                },
            },
        });
    }

    renderSourceChart() {
        const canvas = this.sourceChartRef.el;
        if (!canvas) return;
        if (this.charts.source) this.charts.source.destroy();

        const data = this.state.chartsData.sources || { labels: [], values: [] };
        const ctx = canvas.getContext("2d");

        this.charts.source = new Chart(ctx, {
            type: "doughnut",
            data: {
                labels: data.labels,
                datasets: [
                    {
                        data: data.values,
                        backgroundColor: [
                            "#0f172a", // Dark Slate
                            "#475569", // Slate
                            "#94a3b8", // Light Slate
                            "#cbd5e1", // Platinum
                        ],
                        borderWidth: 2,
                        borderColor: "#ffffff",
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: {
                            boxWidth: 10,
                            padding: 12,
                            font: { size: 11, weight: "500" },
                            color: "#475569",
                        },
                    },
                    tooltip: {
                        backgroundColor: "#0f172a",
                        padding: 10,
                        cornerRadius: 8,
                    },
                },
                cutout: "68%",
            },
        });
    }

    // =========================================================================
    // DRILLDOWN ACTIONS
    // =========================================================================

    openArrivalsToday() {
        const today = new Date().toISOString().split("T")[0];
        const domain = [
            ["check_in", ">=", today + " 00:00:00"],
            ["check_in", "<=", today + " 23:59:59"],
            ["state", "in", ["confirmed", "draft"]],
        ];
        if (this.state.selectedHotelId && this.state.selectedHotelId !== "all") {
            domain.unshift(["hotel_id", "=", parseInt(this.state.selectedHotelId)]);
        }
        this.action.doAction({
            name: _t("Expected Arrivals Today"),
            type: "ir.actions.act_window",
            res_model: "hotel.reservation",
            view_mode: "list,kanban,form",
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            domain: domain,
        });
    }

    openDeparturesToday() {
        const today = new Date().toISOString().split("T")[0];
        const domain = [
            ["check_out", ">=", today + " 00:00:00"],
            ["check_out", "<=", today + " 23:59:59"],
            ["state", "=", "checked_in"],
        ];
        if (this.state.selectedHotelId && this.state.selectedHotelId !== "all") {
            domain.unshift(["hotel_id", "=", parseInt(this.state.selectedHotelId)]);
        }
        this.action.doAction({
            name: _t("Expected Departures Today"),
            type: "ir.actions.act_window",
            res_model: "hotel.reservation",
            view_mode: "list,kanban,form",
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            domain: domain,
        });
    }

    openInHouse() {
        const domain = [["state", "=", "checked_in"]];
        if (this.state.selectedHotelId && this.state.selectedHotelId !== "all") {
            domain.unshift(["hotel_id", "=", parseInt(this.state.selectedHotelId)]);
        }
        this.action.doAction({
            name: _t("In-House Active Stays"),
            type: "ir.actions.act_window",
            res_model: "hotel.reservation",
            view_mode: "list,kanban,form",
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            domain: domain,
        });
    }

    openOverstays() {
        const now = new Date().toISOString().replace("T", " ").substring(0, 19);
        const domain = [
            ["state", "=", "checked_in"],
            ["check_out", "<", now],
        ];
        if (this.state.selectedHotelId && this.state.selectedHotelId !== "all") {
            domain.unshift(["hotel_id", "=", parseInt(this.state.selectedHotelId)]);
        }
        this.action.doAction({
            name: _t("Overstay Alerts"),
            type: "ir.actions.act_window",
            res_model: "hotel.reservation",
            view_mode: "list,kanban,form",
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            domain: domain,
        });
    }

    openRoomsByStatus(status) {
        const domain = [["status", "=", status]];
        if (this.state.selectedHotelId && this.state.selectedHotelId !== "all") {
            domain.unshift(["hotel_id", "=", parseInt(this.state.selectedHotelId)]);
        }
        this.action.doAction({
            name: _t("Hotel Rooms - %s", status.toUpperCase()),
            type: "ir.actions.act_window",
            res_model: "hotel.room",
            view_mode: "kanban,list,form",
            views: [[false, "kanban"], [false, "list"], [false, "form"]],
            domain: domain,
        });
    }

    openHousekeepingTasks() {
        const domain = [["state", "in", ["assigned", "in_progress"]]];
        if (this.state.selectedHotelId && this.state.selectedHotelId !== "all") {
            domain.unshift(["hotel_id", "=", parseInt(this.state.selectedHotelId)]);
        }
        this.action.doAction({
            name: _t("Active Housekeeping Tasks"),
            type: "ir.actions.act_window",
            res_model: "hotel.housekeeping",
            view_mode: "list,kanban,form",
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            domain: domain,
        });
    }

    openMaintenanceTasks() {
        const domain = [["state", "in", ["assigned", "in_progress"]]];
        if (this.state.selectedHotelId && this.state.selectedHotelId !== "all") {
            domain.unshift(["hotel_id", "=", parseInt(this.state.selectedHotelId)]);
        }
        this.action.doAction({
            name: _t("Active Maintenance Requests"),
            type: "ir.actions.act_window",
            res_model: "hotel.maintenance",
            view_mode: "list,kanban,form",
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            domain: domain,
        });
    }

    openPendingFolios() {
        const domain = [
            ["state", "in", ["draft", "open", "partially_paid"]],
            ["balance_amount", ">", 0],
        ];
        this.action.doAction({
            name: _t("Pending Folio Balances"),
            type: "ir.actions.act_window",
            res_model: "hotel.guest.folio",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain: domain,
        });
    }

    openReservation(resId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hotel.reservation",
            res_id: resId,
            views: [[false, "form"]],
        });
    }
}

registry.category("actions").add("hotel_dashboard_main", HotelDashboard);
