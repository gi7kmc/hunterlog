import { GridFilterModel } from "@mui/x-data-grid/models";
import { Qso } from "./QsoTypes";
import { ParkInfo } from "./PotaTypes";
import { Park } from "./Parks";

export interface ContextData {
    qso: Qso | null;
    park: Park | null;
    filter: GridFilterModel;
    bandFilter: number;
    regions: string[];
    regionFilter: string;
    locations: string[];
    locationFilter: string;
    qrtFilter: boolean; // true to filter out QRT spots
    huntedFilter: boolean; // true to filter out already hunted spots
}

export  interface AppContextType {
    contextData: ContextData;
    setData: (d: ContextData) => void;
}