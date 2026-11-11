package instance;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeSet;

import util.InstanceReader;

public final class CrewDeadheadTest
{
	private static final String[] CLASS_LABELS =
			{ "zero", "<=30", "30-60", "60-90", "90-120", "120-180", "180-240", ">240" };
	private static final double[] CLASS_UPPER =
			{ 0.0, 30.0, 60.0, 90.0, 120.0, 180.0, 240.0, Double.POSITIVE_INFINITY };
	private static final double EPS = 1.0e-9;

	private static int failures = 0;

	public static void main(String[] args) throws IOException
	{
		if (args.length < 4)
		{
			System.err.println("uso: CrewDeadheadTest <network-shortestpaths.json> <instance.tsv>"
					+ " <duty_returns.csv> <counts_by_class.csv>");
			System.exit(2);
		}
		Path network = Path.of(args[0]);
		Path instanceFile = Path.of(args[1]);
		Path dutyReturns = Path.of(args[2]);
		Path counts = Path.of(args[3]);
		String instanceName = instanceFile.getFileName().toString().replaceAll("\\.[^.]*$", "");
		String shortName = instanceName.replace("Transformed-", "");

		System.setProperty("crew.network", network.toString());
		Instance instance = InstanceReader.readInstanceFromFile(instanceFile.toString());
		CrewDeadhead cap = instance.getCrewDeadhead();
		check("CrewDeadhead costruito da -Dcrew.network", cap != null, true);
		if (cap == null)
		{
			System.exit(1);
		}

		TreeSet<Integer> stations = new TreeSet<>();
		for (Task task : instance.getTasks())
		{
			stations.add(task.getStartStation());
			stations.add(task.getEndStation());
		}
		int pairs = stations.size() * stations.size();
		System.out.println(instanceName + ": " + instance.getTasks().size() + " task, "
				+ stations.size() + " stazioni, " + pairs + " coppie ordinate");

		CrewDeadhead zero =
				new CrewDeadhead(network, stations, 0.0, CrewDeadhead.DEFAULT_SPEED_KMH);
		int zeroDistance = 0;
		for (int from : stations)
		{
			for (int to : stations)
			{
				if (from != to && cap.minutesBetween(from, to) == 0.0)
				{
					zeroDistance++;
				}
			}
		}
		System.out.println("coppie distinte a distanza nulla nella rete: " + zeroDistance);
		check("limite 0: ammesse le stazioni identiche piu' le coppie a distanza nulla",
				zero.countAllowedPairs(), stations.size() + zeroDistance);

		CrewDeadhead huge =
				new CrewDeadhead(network, stations, 1.0e9, CrewDeadhead.DEFAULT_SPEED_KMH);
		int allowedHuge = huge.countAllowedPairs();
		System.out.println("limite enorme: ammesse " + allowedHuge + " su " + pairs
				+ ", non prezzabili " + (pairs - allowedHuge));
		check("limite enorme: tutte le coppie prezzabili ammesse",
				allowedHuge > 0 && allowedHuge <= pairs, true);

		int asymmetric = 0;
		for (int from : stations)
		{
			for (int to : stations)
			{
				if (Double.compare(cap.minutesBetween(from, to), cap.minutesBetween(to, from)) != 0)
				{
					asymmetric++;
				}
			}
		}
		System.out.println("coppie con minuti diversi nei due versi: " + asymmetric);
		check("matrice non simmetrizzata", asymmetric > 0, true);

		Map<String, Integer> observed = new LinkedHashMap<>();
		for (String label : CLASS_LABELS)
		{
			observed.put(label, 0);
		}
		int mismatched = 0;
		int unpriceable = 0;
		int overCap = 0;
		int duties = 0;
		double worst = 0.0;
		for (String[] row : readCsv(dutyReturns, "start_station", "end_station", "time_minutes",
				"status"))
		{
			if (!"ok".equals(row[3]))
			{
				continue;
			}
			int startStation = Integer.parseInt(row[0]);
			int endStation = Integer.parseInt(row[1]);
			double expected = Double.parseDouble(row[2]);
			double actual = cap.minutesBetween(endStation, startStation);
			duties++;
			if (Double.isNaN(actual))
			{
				unpriceable++;
				continue;
			}
			worst = Math.max(worst, Math.abs(actual - expected));
			if (Math.abs(actual - expected) > 0.01)
			{
				mismatched++;
			}
			if (!cap.isAllowed(endStation, startStation))
			{
				overCap++;
			}
			observed.merge(classOf(actual), 1, Integer::sum);
		}
		System.out.println("duty della run originale confrontate: " + duties
				+ ", scarto massimo " + String.format("%.4f", worst) + " min");
		check("minuti identici a quelli misurati sulla run", mismatched, 0);
		check("coppie delle duty originali non prezzabili", unpriceable, 0);
		System.out.println("duty oltre il limite di " + Parameters.MAX_CREW_DEADHEAD + " min: "
				+ overCap + " su " + duties);
		check("duty oltre il limite", overCap > 0, true);

		Map<String, Integer> expectedClasses = readClassCounts(counts, shortName);
		check("istanza " + shortName + " presente in counts_by_class.csv",
				!expectedClasses.isEmpty(), true);
		for (String label : CLASS_LABELS)
		{
			check("classe " + label, observed.get(label), expectedClasses.getOrDefault(label, 0));
		}

		System.out.println(failures == 0 ? "TUTTI I TEST PASSATI" : failures + " TEST FALLITI");
		System.exit(failures == 0 ? 0 : 1);
	}

	private static String classOf(double minutes)
	{
		for (int i = 0; i < CLASS_LABELS.length; i++)
		{
			if (minutes <= CLASS_UPPER[i] + EPS)
			{
				return CLASS_LABELS[i];
			}
		}
		return CLASS_LABELS[CLASS_LABELS.length - 1];
	}

	private static List<String[]> readCsv(Path path, String... columns) throws IOException
	{
		List<String> lines = Files.readAllLines(path);
		String[] header = lines.get(0).split(",", -1);
		int[] index = new int[columns.length];
		for (int c = 0; c < columns.length; c++)
		{
			index[c] = -1;
			for (int h = 0; h < header.length; h++)
			{
				if (header[h].trim().equals(columns[c]))
				{
					index[c] = h;
				}
			}
			if (index[c] < 0)
			{
				throw new IOException("colonna assente in " + path + ": " + columns[c]);
			}
		}
		List<String[]> rows = new ArrayList<>();
		for (int l = 1; l < lines.size(); l++)
		{
			if (lines.get(l).isBlank())
			{
				continue;
			}
			String[] cells = lines.get(l).split(",", -1);
			String[] row = new String[columns.length];
			for (int c = 0; c < columns.length; c++)
			{
				row[c] = cells[index[c]].trim();
			}
			rows.add(row);
		}
		return rows;
	}

	private static Map<String, Integer> readClassCounts(Path path, String instance)
		throws IOException
	{
		Map<String, Integer> result = new LinkedHashMap<>();
		List<String> lines = Files.readAllLines(path);
		String[] header = lines.get(0).split(",", -1);
		for (int l = 1; l < lines.size(); l++)
		{
			String[] cells = lines.get(l).split(",", -1);
			if (!cells[0].trim().equals(instance))
			{
				continue;
			}
			for (int h = 1; h < header.length && h < cells.length; h++)
			{
				result.put(header[h].trim(), Integer.parseInt(cells[h].trim()));
			}
		}
		return result;
	}

	private static void check(String what, Object actual, Object expected)
	{
		boolean ok = actual.equals(expected);
		if (!ok)
		{
			failures++;
		}
		System.out.println((ok ? "[ok]   " : "[FAIL] ") + what
				+ " (atteso " + expected + ", trovato " + actual + ")");
	}
}
