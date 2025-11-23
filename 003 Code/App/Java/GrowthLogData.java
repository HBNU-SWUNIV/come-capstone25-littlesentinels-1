package com.example.growvision20;

public class GrowthLogData {
    public String datetime, n_cumul_total, n_current_total,
            n_cumul_mature, n_current_mature,
            n_cumul_harvest, n_current_harvest,
            n_cumul_ratio, n_current_ratio;
    public GrowthLogData(String datetime,
                         long n_cumul_total, long n_current_total,
                         long n_cumul_mature, long n_current_mature,
                         long n_cumul_harvest, long n_current_harvest) {

        this.datetime = datetime;
        this.n_cumul_total = String.valueOf(n_cumul_total);
        this.n_current_total = String.valueOf(n_current_total);
        this.n_cumul_mature = String.valueOf(n_cumul_mature);
        this.n_current_mature = String.valueOf(n_current_mature);
        this.n_cumul_harvest = String.valueOf(n_cumul_harvest);
        this.n_current_harvest = String.valueOf(n_current_harvest);
        this.n_cumul_ratio = String.format("%.2f", (double) n_cumul_mature / n_cumul_total * 100) + "%";
        this.n_current_ratio = String.format("%.2f", (double) n_current_mature / n_current_total * 100) + "%";
    }
}
