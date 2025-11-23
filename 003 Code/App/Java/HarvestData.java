package com.example.growvision20;
public class HarvestData {
    public String n_total, n_mature, n_immature, n_harvest;
    public HarvestData(long n_total, long n_mature, long n_immature, long n_harvest) {
        this.n_total = String.valueOf(n_total);
        this.n_mature = String.valueOf(n_mature);
        this.n_immature = String.valueOf(n_immature);
        this.n_harvest = String.valueOf(n_harvest);
    }
}

