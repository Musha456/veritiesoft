/** @odoo-module **/

import { Component, onMounted, onWillUnmount, proxy, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class HotelTaskTimer extends Component {
    static template = "vs_hotel_management.HotelTaskTimer";
    props = useProps({ ...standardFieldProps });

    setup() {
        this.state = proxy({ elapsed: 0 });
        this.interval = null;

        this.updateElapsed = () => {
            const record = this.props?.record;
            if (!record || !record.data) {
                this.state.elapsed = 0;
                return;
            }
            const startedAt = record.data.started_at;
            const completedAt = record.data.completed_at;
            const taskState = record.data.state;

            if (!startedAt) {
                this.state.elapsed = 0;
                return;
            }

            const start = this.toTimestamp(startedAt);
            const end =
                taskState === "in_progress"
                    ? Date.now()
                    : completedAt
                      ? this.toTimestamp(completedAt)
                      : start;

            if (!Number.isFinite(start) || !Number.isFinite(end)) {
                this.state.elapsed = 0;
                return;
            }

            this.state.elapsed = Math.max(
                0,
                Math.floor((end - start) / 1000)
            );
        };

        onMounted(() => {
            this.updateElapsed();
            this.interval = setInterval(this.updateElapsed, 1000);
        });

        onWillUnmount(() => {
            if (this.interval) {
                clearInterval(this.interval);
                this.interval = null;
            }
        });
    }

    toTimestamp(value) {
        if (!value) {
            return NaN;
        }

        // Odoo may provide a Luxon DateTime object.
        if (typeof value.toMillis === "function") {
            return value.toMillis();
        }

        // Handle native JavaScript Date objects.
        if (value instanceof Date) {
            return value.getTime();
        }

        // Handle string values.
        return new Date(value).getTime();
    }

    get formattedTime() {
        const total = this.state.elapsed;
        const hours = Math.floor(total / 3600);
        const minutes = Math.floor((total % 3600) / 60);
        const seconds = total % 60;

        return [hours, minutes, seconds]
            .map((value) => String(value).padStart(2, "0"))
            .join(":");
    }

    get totalSeconds() {
        return this.state.elapsed;
    }

    get isTaskInProgress() {
        return Boolean(this.props?.record?.data?.state === "in_progress");
    }
}

registry.category("fields").add("hotel_task_timer", {
    component: HotelTaskTimer,
});
