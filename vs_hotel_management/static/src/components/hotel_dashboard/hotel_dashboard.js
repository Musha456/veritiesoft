/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUnmount, proxy, signal } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class HotelDashboard extends Component {
    static template = "vs_hotel_management.HotelDashboard";

    trendChartRef = signal.ref();
    sourceChartRef = signal.ref();
    revenueChartRef = signal.ref();
    roomStatusChartRef = signal.ref();

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.charts = {};

        this.state = proxy({
            isLoading: true,
            selectedHotelId: "all",
            selectedPreset: "this_month",
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

    renderAllCharts() {
        if (typeof Chart === "undefined") {
            return;
        }
        this.renderTrendChart();
        this.renderSourceChart();
        this.renderRevenueChart();
        this.renderRoomStatusChart();
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

        const data = this.state.chartsData.trend_7d || { labels: [], occupied: [], revenue: [] };
        const ctx = canvas.getContext("2d");

        this.charts.trend = new Chart(ctx, {
            type: "bar",
            data: {
                labels: data.labels,
                datasets: [
                    {
                        label: _t("Occupied Rooms"),
                        data: data.occupied,
                        backgroundColor: "rgba(59, 130, 246, 0.65)",
                        borderColor: "#3b82f6",
                        borderWidth: 1,
                        borderRadius: 6,
                        yAxisID: "yRooms",
                    },
                    {
                        label: _t("Room Revenue"),
                        data: data.revenue,
                        type: "line",
                        borderColor: "#10b981",
                        backgroundColor: "rgba(16, 185, 129, 0.12)",
                        borderWidth: 3,
                        pointBackgroundColor: "#10b981",
                        pointRadius: 4,
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
                    legend: { position: "top", labels: { boxWidth: 12, font: { weight: "600" } } },
                },
                scales: {
                    yRooms: {
                        type: "linear",
                        display: true,
                        position: "left",
                        title: { display: true, text: _t("Occupied Rooms") },
                        grid: { color: "#f1f5f9" },
                    },
                    yRev: {
                        type: "linear",
                        display: true,
                        position: "right",
                        title: { display: true, text: _t("Revenue") },
                        grid: { drawOnChartArea: false },
                    },
                },
            },
        });
    }

    renderSourceChart() {
        const canvas = this.sourceChartRef.el;
        if (!canvas) return;
        if (this.charts.source) this.charts.source.destroy();

        const data = this.state.chartsData.booking_sources || { labels: [], values: [] };
        const ctx = canvas.getContext("2d");

        this.charts.source = new Chart(ctx, {
            type: "doughnut",
            data: {
                labels: data.labels,
                datasets: [
                    {
                        data: data.values,
                        backgroundColor: [
                            "#3b82f6",
                            "#10b981",
                            "#f59e0b",
                            "#ef4444",
                            "#8b5cf6",
                            "#06b6d4",
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
                    legend: { position: "bottom", labels: { boxWidth: 12, padding: 12 } },
                },
                cutout: "68%",
            },
        });
    }

    renderRevenueChart() {
        const canvas = this.revenueChartRef.el;
        if (!canvas) return;
        if (this.charts.revenue) this.charts.revenue.destroy();

        const data = this.state.chartsData.revenue_breakdown || { labels: [], values: [] };
        const ctx = canvas.getContext("2d");

        this.charts.revenue = new Chart(ctx, {
            type: "bar",
            data: {
                labels: data.labels,
                datasets: [
                    {
                        label: _t("Revenue Amount"),
                        data: data.values,
                        backgroundColor: [
                            "rgba(59, 130, 246, 0.75)",
                            "rgba(245, 158, 11, 0.75)",
                            "rgba(16, 185, 129, 0.75)",
                            "rgba(139, 92, 246, 0.75)",
                            "rgba(239, 68, 68, 0.75)",
                        ],
                        borderRadius: 6,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: "#f1f5f9" },
                    },
                },
            },
        });
    }

    renderRoomStatusChart() {
        const canvas = this.roomStatusChartRef.el;
        if (!canvas) return;
        if (this.charts.roomStatus) this.charts.roomStatus.destroy();

        const data = this.state.chartsData.room_status || { labels: [], values: [] };
        const ctx = canvas.getContext("2d");

        this.charts.roomStatus = new Chart(ctx, {
            type: "doughnut",
            data: {
                labels: data.labels,
                datasets: [
                    {
                        data: data.values,
                        backgroundColor: [
                            "#10b981", // Available / Clean
                            "#3b82f6", // Occupied
                            "#ef4444", // Dirty
                            "#8b5cf6", // Cleaning
                            "#f59e0b", // Maintenance
                            "#64748b", // Out of order
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
                    legend: { position: "bottom", labels: { boxWidth: 10, padding: 10 } },
                },
                cutout: "62%",
            },
        });
    }

    // =========================================================================
    // DRILLDOWN ACTIONS (Interactive Navigation)
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
