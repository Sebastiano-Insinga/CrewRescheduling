package instance;

import java.io.IOException;
import java.io.Reader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Collection;
import java.util.HashMap;
import java.util.Map;
import java.util.TreeSet;

import com.google.gson.stream.JsonReader;
import com.google.gson.stream.JsonToken;

public final class CrewDeadhead
{
	public static final double DEFAULT_SPEED_KMH = 57.0;

	private final int[] denseToId;
	private final int[] idToDense;
	private final int minId;
	private final double[][] minutes;
	private final double limit;

	public static CrewDeadhead fromSystemProperties(Collection<Integer> stations) throws IOException
	{
		String network = System.getProperty("crew.network");
		if (network == null || network.isBlank())
		{
			System.out.println("crew deadhead: -Dcrew.network assente, nessun limite sul rientro");
			return null;
		}
		double limit = Parameters.MAX_CREW_DEADHEAD;
		double speed = Double.parseDouble(System.getProperty("crew.speed",
				Double.toString(DEFAULT_SPEED_KMH)));
		return new CrewDeadhead(Path.of(network), stations, limit, speed);
	}

	public CrewDeadhead(Path network, Collection<Integer> stations, double limit, double speedKmh)
		throws IOException
	{
		this.limit = limit;

		TreeSet<Integer> sorted = new TreeSet<>(stations);
		this.denseToId = new int[sorted.size()];
		int next = 0;
		for (int id : sorted)
		{
			denseToId[next++] = id;
		}
		this.minId = denseToId.length == 0 ? 0 : denseToId[0];
		int maxId = denseToId.length == 0 ? 0 : denseToId[denseToId.length - 1];
		this.idToDense = new int[maxId - minId + 1];
		for (int i = 0; i < idToDense.length; i++)
		{
			idToDense[i] = -1;
		}
		for (int i = 0; i < denseToId.length; i++)
		{
			idToDense[denseToId[i] - minId] = i;
		}

		Map<Long, Double> weights = readWeights(network, sorted);

		int n = denseToId.length;
		this.minutes = new double[n][n];
		int same = 0;
		int direct = 0;
		int reversed = 0;
		int absent = 0;
		double min = Double.POSITIVE_INFINITY;
		double max = 0.0;
		double sum = 0.0;
		int counted = 0;
		for (int i = 0; i < n; i++)
		{
			for (int j = 0; j < n; j++)
			{
				if (i == j)
				{
					minutes[i][j] = 0.0;
					same++;
					continue;
				}
				Double weight = weights.get(key(denseToId[i], denseToId[j]));
				if (weight != null)
				{
					direct++;
				}
				else
				{
					weight = weights.get(key(denseToId[j], denseToId[i]));
					if (weight != null)
					{
						reversed++;
					}
				}
				if (weight == null)
				{
					minutes[i][j] = Double.NaN;
					absent++;
					continue;
				}
				double value = weight / 1000.0 / speedKmh * 60.0;
				minutes[i][j] = value;
				min = Math.min(min, value);
				max = Math.max(max, value);
				sum += value;
				counted++;
			}
		}

		System.out.printf(
				"crew deadhead: stazioni=%d coppie=%d identiche=%d dirette=%d inverse=%d assenti=%d%n",
				n, n * n, same, direct, reversed, absent);
		System.out.printf(
				"crew deadhead: limite=%.1f min velocita=%.1f km/h minuti min=%.2f max=%.2f media=%.2f%n",
				limit, speedKmh, counted == 0 ? 0.0 : min, max, counted == 0 ? 0.0 : sum / counted);
	}

	public boolean isAllowed(int endStation, int startStation)
	{
		double value = minutesBetween(endStation, startStation);
		return value <= limit;
	}

	public double minutesBetween(int endStation, int startStation)
	{
		int i = dense(endStation);
		int j = dense(startStation);
		if (i < 0 || j < 0)
		{
			return Double.NaN;
		}
		return minutes[i][j];
	}

	public double getLimit()
	{
		return limit;
	}

	public int getNumStations()
	{
		return denseToId.length;
	}

	public int countAllowedPairs()
	{
		int allowed = 0;
		for (int i = 0; i < denseToId.length; i++)
		{
			for (int j = 0; j < denseToId.length; j++)
			{
				if (minutes[i][j] <= limit)
				{
					allowed++;
				}
			}
		}
		return allowed;
	}

	private int dense(int station)
	{
		int offset = station - minId;
		if (offset < 0 || offset >= idToDense.length)
		{
			return -1;
		}
		return idToDense[offset];
	}

	private static long key(int from, int to)
	{
		return (((long) from) << 32) | (to & 0xffffffffL);
	}

	private static Map<Long, Double> readWeights(Path network, TreeSet<Integer> stations)
		throws IOException
	{
		Map<Long, Double> weights = new HashMap<>();
		try (Reader in = Files.newBufferedReader(network, StandardCharsets.UTF_8);
				JsonReader reader = new JsonReader(in))
		{
			reader.beginObject();
			while (reader.hasNext())
			{
				int from = parseStation(reader.nextName());
				if (from < 0 || !stations.contains(from))
				{
					reader.skipValue();
					continue;
				}
				reader.beginObject();
				while (reader.hasNext())
				{
					int to = parseStation(reader.nextName());
					if (to < 0 || !stations.contains(to))
					{
						reader.skipValue();
						continue;
					}
					Double weight = readWeight(reader);
					if (weight != null)
					{
						weights.put(key(from, to), weight);
					}
				}
				reader.endObject();
			}
			reader.endObject();
		}
		return weights;
	}

	private static Double readWeight(JsonReader reader) throws IOException
	{
		Double weight = null;
		reader.beginObject();
		while (reader.hasNext())
		{
			if ("weight".equals(reader.nextName()) && reader.peek() == JsonToken.NUMBER)
			{
				weight = reader.nextDouble();
			}
			else
			{
				reader.skipValue();
			}
		}
		reader.endObject();
		return weight;
	}

	private static int parseStation(String name)
	{
		try
		{
			return Integer.parseInt(name);
		}
		catch (NumberFormatException e)
		{
			return -1;
		}
	}
}
