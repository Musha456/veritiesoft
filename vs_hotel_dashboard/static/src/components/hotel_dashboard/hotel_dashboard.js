/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUnmount, proxy, signal } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class HotelDashboard extends Component {
    static template = "vs_hotel_dashboard.HotelDashboard";

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
                    date_from: this.state.customDateFrom,
                    date_to: this.state.customDateTo,
                    preset: this.state.selectedPreset,
                }
            );

            this.state.hotels = data.hotels || [];
            this.state.selectedHotelId = data.selected_hotel_id || "all";
            this.state.selectedPreset = data.selected_preset || "this_month";
            this.state.customDateFrom = data.date_from || "";
            this.state.customDateTo = data.date_to || "";
            this.state.currencySymbol = data.currency_symbol || "$";
            this.state.kpis = data.kpis || {};
            this.state.queues = data.queues || {};
            this.state.housekeeping = data.housekeeping || {};
            this.state.chartsData = data.charts || {};
            this.state.upcomingArrivals = data.upcoming_arrivals || [];
            this.state.upcomingDepartures = data.upcoming_departures || [];
        } catch (error) {
            console.error("Error loading hotel dashboard data:", error);
            this.notification.add(_t("Could not load hotel dashboard analytics."), {
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

    async onCustomDateApply() {
        if (this.state.customDateFrom && this.state.customDateTo) {
            this.state.selectedPreset = "custom";
            await this.reload();
        }
    }

    // ==========================================
    // Chart.js Rendering
    // ==========================================
    destroyAllCharts() {
        Object.keys(this.charts).forEach((key) => {
            if (this.charts[key]) {
                this.charts[key].destroy();
                delete this.charts[key];
            }
        });
    }

    renderAllCharts() {
        if (typeof Chart === "undefined") {
            console.warn("Chart.js not available yet in browser runtime.");
            return;
        }

        this.destroyAllCharts();

        // 1. 7-Day Occupancy & Revenue Trend Chart
        const trendEl = this.trendChartRef();
        if (trendEl && this.state.chartsData.trend) {
            const trendCtx = trendEl.getContext("2d");
            this.charts.trend = new Chart(trendCtx, {
                data: this.state.chartsData.trend,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: "top" },
                        tooltip: { mode: "index", intersect: false },
                    },
                    scales: {
                        y: {
                            type: "linear",
                            position: "left",
                            title: { display: true, text: _t("Occupied Rooms") },
                            beginAtZero: true,
                            ticks: { precision: 0 },
                        },
                        y1: {
                            type: "linear",
                            position: "right",
                            title: { display: true, text: _t("Revenue") },
                            beginAtZero: true,
                            grid: { drawOnChartArea: false },
                        },
                    },
                },
            });
        }

        // 2. Booking Sources Donut Chart
        const sourceEl = this.sourceChartRef();
        if (sourceEl && this.state.chartsData.sources) {
            const sourceCtx = sourceEl.getContext("2d");
            this.charts.sources = new Chart(sourceCtx, {
                type: "doughnut",
                data: this.state.chartsData.sources,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: "right" },
                    },
                    cutout: "68%",
                },
            });
        }

        // 3. Department Revenue Bar Chart
        const revEl = this.revenueChartRef();
        if (revEl && this.state.chartsData.departments) {
            const revCtx = revEl.getContext("2d");
            this.charts.revenue = new Chart(revCtx, {
                type: "bar",
                data: this.state.chartsData.departments,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: { display: true, text: _t("Amount") },
                        },
                    },
                },
            });
        }

        // 4. Room Status Distribution Donut Chart
        const roomEl = this.roomStatusChartRef();
        if (roomEl && this.state.chartsData.room_status) {
            const roomCtx = roomEl.getContext("2d");
            this.charts.roomStatus = new Chart(roomCtx, {
                type: "doughnut",
                data: this.state.chartsData.room_status,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: "right" },
                    },
                    cutout: "62%",
                },
            });
        }
    }

    // ==========================================
    // 1-Click Interactive Drilldown Actions
    // ==========================================
    _getHotelDomain() {
        if (this.state.selectedHotelId && this.state.selectedHotelId !== "all") {
            return [["hotel_id", "=", parseInt(this.state.selectedHotelId)]];
        }
        return [];
    }

    openArrivalsToday() {
        const todayStr = new Date().toISOString().slice(0, 10);
        const domain = [
            ...this._getHotelDomain(),
            ["check_in", ">=", `${todayStr} 00:00:00`],
            ["check_in", "<=", `${todayStr} 23:59:59`],
            ["state", "in", ["draft", "confirmed"]],
        ];
        this.action.doAction({
            name: _t("Today's Expected Arrivals"),
            type: "ir.actions.act_window",
            res_model: "hotel.reservation",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain: domain,
        });
    }

    openDeparturesToday() {
        const todayStr = new Date().toISOString().slice(0, 10);
        const domain = [
            ...this._getHotelDomain(),
            ["check_out", ">=", `${todayStr} 00:00:00`],
            ["check_out", "<=", `${todayStr} 23:59:59`],
            ["state", "=", "check_in"],
        ];
        this.action.doAction({
            name: _t("Today's Expected Departures"),
            type: "ir.actions.act_window",
            res_model: "hotel.reservation",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain: domain,
        });
    }

    openInHouse() {
        const domain = [
            ...this._getHotelDomain(),
            ["state", "=", "check_in"],
        ];
        this.action.doAction({
            name: _t("In-House Guests"),
            type: "ir.actions.act_window",
            res_model: "hotel.reservation",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain: domain,
        });
    }

    openOverstays() {
        const nowStr = new Date().toISOString().slice(0, 19).replace("T", " ");
        const domain = [
            ...this._getHotelDomain(),
            ["state", "=", "check_in"],
            ["check_out", "<", nowStr],
        ];
        this.action.doAction({
            name: _t("Overstay Stays"),
            type: "ir.actions.act_window",
            res_model: "hotel.reservation",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain: domain,
        });
    }

    openRoomsByStatus(status) {
        const domain = [
            ...this._getHotelDomain(),
            ["status", "=", status],
        ];
        this.action.doAction({
            name: _t("Hotel Rooms - ") + status.toUpperCase(),
            type: "ir.actions.act_window",
            res_model: "hotel.room",
            view_mode: "kanban,list,form",
            views: [[false, "kanban"], [false, "list"], [false, "form"]],
            domain: domain,
        });
    }

    openHousekeepingTasks() {
        const domain = [
            ...this._getHotelDomain(),
            ["state", "not in", ["done", "cancelled"]],
        ];
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
        const domain = [
            ...this._getHotelDomain(),
            ["state", "not in", ["done", "cancelled"]],
        ];
        this.action.doAction({
            name: _t("Active Maintenance Tasks"),
            type: "ir.actions.act_window",
            res_model: "hotel.maintenance",
            view_mode: "list,kanban,form",
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            domain: domain,
        });
    }

    openPendingFolios() {
        const domain = [
            ...this._getHotelDomain(),
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
