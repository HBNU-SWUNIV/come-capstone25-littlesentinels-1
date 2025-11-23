package com.example.growvision20;

import androidx.lifecycle.MutableLiveData;
import androidx.lifecycle.ViewModel;
public class HarvestViewModel extends ViewModel {
    private final MutableLiveData<HarvestData> live_data = new MutableLiveData<>();
    public void setData(HarvestData data) {
        live_data.setValue(data);
    }
    public MutableLiveData<HarvestData> getData() {
        return live_data;
    }
}
